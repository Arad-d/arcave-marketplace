"""Exercise shopping through HTTP forms and friendly failure handling."""

from unittest.mock import patch

from accounts.models import Customer, ShopOwner
from django.db import OperationalError
from django.test import TestCase
from django.urls import reverse

from .models import Cart, Comment, Order, Product


class CustomerJourneyTests(TestCase):
    """Test the connection between forms, cart actions, receipts and reviews."""

    def setUp(self) -> None:
        """Create a buyer with a product available in one store."""
        self.customer = Customer.objects.create_user(
            username="journey", email="journey@example.com"
        )
        owner = ShopOwner.objects.create(
            name="journey-seller", store_name="Store", password="!"
        )
        self.product = Product.objects.create(
            shop_owner=owner,
            name="Product",
            description="Description",
            price="10.50",
            stock=5,
        )
        self.client.force_login(self.customer)

    def test_cart_to_receipt_and_verified_review(self) -> None:
        """Real form posts add, update, remove, purchase and authorize a review."""
        self.client.post(
            reverse("add_to_cart", args=[self.product.pk]), {"quantity": 2}
        )
        item = Cart.objects.get(customer=self.customer)
        self.client.post(reverse("update_cart", args=[item.pk]), {"quantity": 3})
        item.refresh_from_db()
        self.assertEqual(item.quantity, 3)
        self.client.post(reverse("remove_from_cart", args=[item.pk]))
        self.assertFalse(Cart.objects.filter(customer=self.customer).exists())
        self.client.post(
            reverse("add_to_cart", args=[self.product.pk]), {"quantity": 2}
        )
        cart = self.client.get(reverse("view_cart"))
        response = self.client.post(
            reverse("checkout"),
            {"checkout_token": cart.context["checkout_token"]},
            follow=True,
        )
        order = Order.objects.get(customer=self.customer)
        self.assertContains(response, str(order))
        self.assertContains(response, "Product")
        self.assertFalse(Cart.objects.filter(customer=self.customer).exists())
        self.product.refresh_from_db()
        self.assertEqual(self.product.stock, 3)
        self.client.post(
            reverse("add_comment", args=[self.product.pk]), {"text": "Purchased review"}
        )
        self.assertTrue(
            Comment.objects.filter(
                customer=self.customer, product=self.product
            ).exists()
        )

    def test_failed_checkout_keeps_cart_and_shows_friendly_message(self) -> None:
        """Database failures are logged, never presented as successful purchases."""
        item = Cart.objects.create(customer=self.customer, product=self.product)
        cart = self.client.get(reverse("view_cart"))
        with patch(
            "shop.views.place_order",
            side_effect=OperationalError("private database details"),
        ), self.assertLogs("shop.views", level="ERROR") as captured:
            response = self.client.post(
                reverse("checkout"),
                {"checkout_token": cart.context["checkout_token"]},
                follow=True,
            )
        self.assertContains(response, "ثبت سفارش انجام نشد")
        self.assertNotContains(response, "private database details")
        self.assertTrue(Cart.objects.filter(pk=item.pk).exists())
        self.assertFalse(Order.objects.exists())
        self.assertIsNotNone(captured.records[0].request.error_reference)
