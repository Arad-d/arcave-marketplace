"""Receipt, validation, rollback and real row-lock concurrency regressions."""

from concurrent.futures import ThreadPoolExecutor
from decimal import Decimal
from threading import Barrier
from unittest.mock import patch

from accounts.models import Customer, ShopOwner
from django.db import IntegrityError, close_old_connections, connection, transaction
from django.db.migrations.executor import MigrationExecutor
from django.test import Client, TestCase, TransactionTestCase, skipUnlessDBFeature
from django.urls import reverse

from .forms import ProductForm
from .models import Cart, Comment, Order, Product, Purchase, Reply
from .services import (
    ShoppingError,
    advance_order,
    change_cart,
    checkout_token,
    place_order,
)


class ShoppingFixtures:
    """Create a small shared-stock store and independent customer carts."""

    def setUp(self) -> None:
        """Create fresh records for each test without expensive password hashing."""
        super().setUp()
        self.owner = ShopOwner.objects.create(
            name="seller", store_name="Original store", password="!"
        )
        self.customers = [
            Customer.objects.create(username=f"buyer{i}", email=f"buyer{i}@example.com")
            for i in range(2)
        ]
        self.product = Product.objects.create(
            shop_owner=self.owner,
            name="Original product",
            description="Description",
            price=Decimal("12.50"),
            stock=3,
        )
        self.carts = [
            Cart.objects.create(customer=customer, product=self.product, quantity=2)
            for customer in self.customers
        ]

    def token(self, index: int = 0) -> str:
        """Sign the price and quantities currently visible to one buyer."""
        return checkout_token(
            self.customers[index].pk,
            list(
                Cart.objects.filter(customer=self.customers[index]).select_related(
                    "product"
                )
            ),
        )

    def seller_client(self) -> Client:
        """Create an authenticated seller session without bypassing middleware checks."""
        client = Client()
        session = client.session
        session["shop_owner_id"] = self.owner.pk
        session["shop_owner_auth_hash"] = self.owner.get_session_auth_hash()
        session.save()
        return client


class ShoppingReliabilityTests(ShoppingFixtures, TestCase):
    """Exercise the externally meaningful shopping guarantees."""

    def test_receipt_replay_does_not_purchase_a_new_cart(self) -> None:
        """A retry returns its original receipt even after new items are added."""
        token = self.token()
        order = place_order(self.customers[0].pk, token)
        new_item = Cart.objects.create(customer=self.customers[0], product=self.product)
        repeated = place_order(self.customers[0].pk, token)
        self.assertEqual(order.pk, repeated.pk)
        self.assertTrue(Cart.objects.filter(pk=new_item.pk).exists())
        self.product.refresh_from_db()
        self.assertEqual(self.product.stock, 1)
        self.assertEqual(order.total_price, Decimal("25.00"))
        self.assertEqual(Purchase.objects.count(), 1)

    def test_price_cart_and_identity_changes_require_confirmation(self) -> None:
        """Old or another customer's confirmation never authorizes a changed cart."""
        token = self.token()
        with self.assertRaises(ShoppingError):
            place_order(self.customers[1].pk, token)
        Product.objects.filter(pk=self.product.pk).update(price="15.00")
        with self.assertRaises(ShoppingError):
            place_order(self.customers[0].pk, token)
        token = self.token()
        Cart.objects.filter(pk=self.carts[0].pk).update(quantity=1)
        with self.assertRaises(ShoppingError):
            place_order(self.customers[0].pk, token)
        self.assertFalse(Order.objects.exists())

    def test_invalid_and_expired_tokens_cannot_checkout(self) -> None:
        """Missing, tampered or expired confirmations leave all state intact."""
        for token in ("", self.token() + "tampered"):
            with self.assertRaises(ShoppingError):
                place_order(self.customers[0].pk, token)
        with patch("django.core.signing.time.time", return_value=1):
            expired = self.token()
        with self.assertRaises(ShoppingError):
            place_order(self.customers[0].pk, expired)
        self.assertEqual(Cart.objects.count(), 2)
        self.assertFalse(Order.objects.exists())

    def test_insufficient_stock_cancels_entire_order(self) -> None:
        """One unavailable line prevents all deductions and preserves the cart."""
        other = Product.objects.create(
            shop_owner=self.owner, name="Empty", description="Empty", price="1", stock=0
        )
        Cart.objects.create(customer=self.customers[0], product=other)
        with self.assertRaises(ShoppingError):
            place_order(self.customers[0].pk, self.token())
        self.product.refresh_from_db()
        self.assertEqual(self.product.stock, 3)
        self.assertFalse(Purchase.objects.exists())
        self.assertFalse(Order.objects.exists())
        self.assertEqual(Cart.objects.filter(customer=self.customers[0]).count(), 2)

    def test_database_failure_rolls_back_stock_receipt_and_cart(self) -> None:
        """A failure after stock has been changed rolls back the entire transaction."""
        with patch.object(
            Cart.objects.all().__class__,
            "delete",
            side_effect=IntegrityError("injected"),
        ):
            with self.assertRaises(IntegrityError):
                place_order(self.customers[0].pk, self.token())
        self.product.refresh_from_db()
        self.assertEqual(self.product.stock, 3)
        self.assertEqual(Cart.objects.count(), 2)
        self.assertFalse(Order.objects.exists())
        self.assertFalse(Purchase.objects.exists())

    def test_cart_limits_apply_to_combined_quantity(self) -> None:
        """Repeated adds cannot exceed stock or the per-product limit."""
        with self.assertRaises(ShoppingError):
            change_cart(self.customers[0].pk, product_id=self.product.pk, quantity=2)
        self.carts[0].refresh_from_db()
        self.assertEqual(self.carts[0].quantity, 2)
        change_cart(self.customers[0].pk, product_id=self.product.pk, quantity=1)
        self.carts[0].refresh_from_db()
        self.assertEqual(self.carts[0].quantity, 3)

    def test_invalid_quantities_are_rejected_without_clamping(self) -> None:
        """Bad form values do not silently turn into a different purchase quantity."""
        self.client.force_login(self.customers[0])
        for quantity in ("0", "-1", "6", "1.5", "abc", ""):
            self.client.post(
                reverse("update_cart", args=[self.carts[0].pk]), {"quantity": quantity}
            )
            self.client.post(
                reverse("add_to_cart", args=[self.product.pk]), {"quantity": quantity}
            )
            self.carts[0].refresh_from_db()
            self.assertEqual(self.carts[0].quantity, 2)

    def test_product_validation_and_stale_inventory(self) -> None:
        """Reject invalid product fields and seller edits based on obsolete stock."""
        valid = {
            "name": "Good",
            "description": "Good",
            "price": "10",
            "stock": 3,
            "category": "electronics",
            "original_stock": 3,
        }
        for key, value in (
            ("price", "0"),
            ("price", "NaN"),
            ("stock", "-1"),
            ("stock", "1.5"),
            ("category", "fake"),
            ("name", " "),
            ("description", " "),
        ):
            form = ProductForm(
                {**valid, key: value}, instance=Product.objects.get(pk=self.product.pk)
            )
            self.assertFalse(form.is_valid(), key)
        place_order(self.customers[0].pk, self.token())
        form = ProductForm(valid, instance=Product.objects.get(pk=self.product.pk))
        self.assertFalse(form.is_valid())
        self.assertIn("__all__", form.errors)
        fresh = ProductForm(
            {**valid, "original_stock": 1},
            instance=Product.objects.get(pk=self.product.pk),
        )
        self.assertTrue(fresh.is_valid(), fresh.errors)

    def test_database_rejects_invalid_prices_and_quantities(self) -> None:
        """Direct writes cannot bypass the fundamental numeric invariants."""
        for queryset, values in (
            (Product.objects.all(), {"price": 0}),
            (Product.objects.all(), {"category": "bad"}),
            (Cart.objects.all(), {"quantity": 6}),
            (Cart.objects.all(), {"quantity": 0}),
        ):
            with self.assertRaises(IntegrityError), transaction.atomic():
                queryset.update(**values)

    def test_snapshots_and_both_dashboards_survive_product_deletion(self) -> None:
        """Receipt names, prices and seller sales remain after edits and deletion."""
        order = place_order(self.customers[0].pk, self.token())
        Product.objects.filter(pk=self.product.pk).update(name="Renamed", price="99")
        self.product.delete()
        line = order.items.get()
        self.assertIsNone(line.product_id)
        self.assertEqual(line.product_name, "Original product")
        self.assertEqual(line.store_name, "Original store")
        self.assertEqual(line.unit_price, Decimal("12.50"))
        self.client.force_login(self.customers[0])
        self.assertContains(
            self.client.get(reverse("customer_dashboard")), "Original product"
        )
        self.assertContains(
            self.client.get(reverse("order_detail", args=[order.number])),
            "Original store",
        )
        # Seller middleware authenticates via its stored password fingerprint.
        seller = Client()
        session = seller.session
        session["shop_owner_id"] = self.owner.pk
        session["shop_owner_auth_hash"] = self.owner.get_session_auth_hash()
        session.save()
        response = seller.get(reverse("shop_owner_dashboard"))
        self.assertContains(response, "Original product")

    def test_duplicate_replies_preserve_first_answer(self) -> None:
        """Repeated submissions do not crash or silently overwrite the original reply."""
        comment = Comment.objects.create(
            product=self.product, customer=self.customers[0], text="Question"
        )
        client = self.seller_client()
        url = reverse("reply_to_comment", args=[comment.pk])
        for text in ("First answer", "Replacement"):
            self.assertEqual(client.post(url, {"text": text}).status_code, 302)
        self.assertEqual(Reply.objects.filter(comment=comment).count(), 1)
        self.assertEqual(comment.reply.text, "First answer")

    def test_empty_messages_are_rejected(self) -> None:
        """Whitespace and oversized messages create neither reviews nor replies."""
        place_order(self.customers[0].pk, self.token())
        self.client.force_login(self.customers[0])
        for text in ("   ", "x" * 2001):
            self.client.post(
                reverse("add_comment", args=[self.product.pk]), {"text": text}
            )
        self.assertFalse(Comment.objects.exists())
        comment = Comment.objects.create(
            product=self.product, customer=self.customers[0], text="Question"
        )
        client = self.seller_client()
        for text in ("   ", "x" * 2001):
            client.post(reverse("reply_to_comment", args=[comment.pk]), {"text": text})
        self.assertFalse(Reply.objects.exists())

    def test_seller_edit_cannot_restore_sold_inventory(self) -> None:
        """A seller form opened before checkout must be refreshed before saving stock."""
        client = self.seller_client()
        url = reverse("edit_product", args=[self.product.pk])
        response = client.get(url)
        original = response.context["form"]["original_stock"].value()
        place_order(self.customers[0].pk, self.token())
        response = client.post(
            url,
            {
                "name": "Changed",
                "description": "Changed",
                "price": "12.50",
                "stock": 3,
                "original_stock": original,
                "category": "electronics",
            },
        )
        self.assertEqual(response.status_code, 200)
        self.product.refresh_from_db()
        self.assertEqual(self.product.stock, 1)
        self.assertEqual(self.product.name, "Original product")

    def test_admin_edit_requires_fresh_stock_and_orders_are_read_only(self) -> None:
        """The administrator interface cannot accidentally restore sold stock or alter receipts."""
        admin = Customer.objects.create_superuser(
            username="admin", email="admin@example.com", password="test-password"
        )
        self.client.force_login(admin)
        url = reverse("admin:shop_product_change", args=[self.product.pk])
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        place_order(self.customers[0].pk, self.token())
        data = {
            "name": "Changed",
            "description": "Changed",
            "price": "12.50",
            "stock": 3,
            "original_stock": 3,
            "category": "electronics",
            "shop_owner": self.owner.pk,
            "_save": "Save",
        }
        self.assertEqual(self.client.post(url, data).status_code, 200)
        self.product.refresh_from_db()
        self.assertEqual(self.product.stock, 1)
        data["original_stock"] = 1
        self.assertEqual(self.client.post(url, data).status_code, 302)
        self.product.refresh_from_db()
        self.assertEqual(self.product.stock, 3)
        line = Purchase.objects.get()
        self.assertEqual(
            self.client.post(
                reverse("admin:shop_purchase_change", args=[line.pk]), {"quantity": 5}
            ).status_code,
            403,
        )

    def test_order_privacy_and_status(self) -> None:
        """Other customers cannot read receipts; status advances without changing money."""
        order = place_order(self.customers[0].pk, self.token())
        self.client.force_login(self.customers[1])
        self.assertEqual(
            self.client.get(reverse("order_detail", args=[order.number])).status_code,
            404,
        )
        self.assertEqual(order.status, Order.Status.PLACED)
        advance_order(order.pk)
        order.refresh_from_db()
        self.assertEqual(order.status, Order.Status.PROCESSING)
        advance_order(order.pk)
        advance_order(order.pk)
        order.refresh_from_db()
        self.assertEqual(order.status, Order.Status.COMPLETED)
        self.assertEqual(order.total_price, Decimal("25.00"))


@skipUnlessDBFeature("has_select_for_update")
class ShoppingConcurrencyTests(ShoppingFixtures, TransactionTestCase):
    """Use independent database connections to exercise PostgreSQL row locks."""

    def race(self, jobs: list) -> list:
        """Start operations together, closing each worker's database connection."""
        barrier = Barrier(len(jobs))

        def run(job):
            """Run a checkout independently and return a stable outcome."""
            close_old_connections()
            try:
                barrier.wait(timeout=10)
                return place_order(*job).pk
            except ShoppingError:
                return None
            finally:
                close_old_connections()

        with ThreadPoolExecutor(max_workers=len(jobs)) as pool:
            return list(pool.map(run, jobs))

    def test_two_buyers_cannot_oversell(self) -> None:
        """Two buyers wanting two units cannot both acquire stock of three."""
        result = self.race(
            [(customer.pk, self.token(i)) for i, customer in enumerate(self.customers)]
        )
        self.assertEqual(sum(value is not None for value in result), 1)
        self.product.refresh_from_db()
        self.assertEqual(self.product.stock, 1)
        self.assertEqual(Purchase.objects.count(), 1)
        self.assertEqual(Cart.objects.count(), 1)

    def test_concurrent_duplicate_requests_return_one_order(self) -> None:
        """Double-click requests sharing a token both resolve to the same order."""
        job = (self.customers[0].pk, self.token())
        result = self.race([job, job])
        self.assertIsNotNone(result[0])
        self.assertEqual(result[0], result[1])
        self.assertEqual(Order.objects.count(), 1)
        self.product.refresh_from_db()
        self.assertEqual(self.product.stock, 1)

    def test_separate_tabs_cannot_checkout_the_same_cart_twice(self) -> None:
        """Different tokens from two tabs still serialize on the customer."""
        result = self.race(
            [(self.customers[0].pk, self.token()), (self.customers[0].pk, self.token())]
        )
        self.assertEqual(sum(value is not None for value in result), 1)
        self.assertEqual(Order.objects.count(), 1)

    def test_concurrent_replies_have_one_winner(self) -> None:
        """The unique reply constraint handles two legitimate HTTP submissions gracefully."""
        comment = Comment.objects.create(
            product=self.product, customer=self.customers[0], text="Question"
        )
        clients = [self.seller_client(), self.seller_client()]
        barrier = Barrier(2)

        def reply(index: int) -> int:
            """Submit through a separate session and connection."""
            close_old_connections()
            try:
                barrier.wait(timeout=10)
                return (
                    clients[index]
                    .post(
                        reverse("reply_to_comment", args=[comment.pk]),
                        {"text": f"Answer {index}"},
                    )
                    .status_code
                )
            finally:
                close_old_connections()

        with ThreadPoolExecutor(max_workers=2) as pool:
            self.assertEqual(list(pool.map(reply, range(2))), [302, 302])
        self.assertEqual(Reply.objects.filter(comment=comment).count(), 1)


class PurchaseMigrationTests(TransactionTestCase):
    """Exercise backfill with historical rows, including an unknown original price."""

    def test_legacy_receipts_preserve_known_and_unknown_totals(self) -> None:
        """Backfill never substitutes today's catalog price for unknown historical money."""
        executor = MigrationExecutor(connection)
        latest = executor.loader.graph.leaf_nodes()
        old = [node for node in latest if node[0] != "shop"] + [
            ("shop", "0003_product_category")
        ]
        executor.migrate(old)
        try:
            apps = executor.loader.project_state(old).apps
            customer = apps.get_model("accounts", "Customer").objects.create(
                username="legacy"
            )
            owner = apps.get_model("accounts", "ShopOwner").objects.create(
                name="legacy", store_name="Legacy", password="!"
            )
            product = apps.get_model("shop", "Product").objects.create(
                shop_owner=owner, name="Legacy product", price="99", stock=1
            )
            purchase_model = apps.get_model("shop", "Purchase")
            known = purchase_model.objects.create(
                customer=customer, product=product, quantity=2, total_price="10"
            )
            unknown = purchase_model.objects.create(
                customer=customer, product=product, quantity=1, total_price=None
            )
            MigrationExecutor(connection).migrate(latest)
            line = Purchase.objects.get(pk=known.pk)
            self.assertEqual(line.unit_price, Decimal("5"))
            self.assertEqual(line.order.created_at, known.created_at)
            self.assertEqual(line.order.status, Order.Status.LEGACY)
            line = Purchase.objects.get(pk=unknown.pk)
            self.assertIsNone(line.unit_price)
            self.assertIsNone(line.order.total_price)
        finally:
            MigrationExecutor(connection).migrate(latest)
