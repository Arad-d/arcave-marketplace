"""Regression tests for seller credentials and account-bound password recovery."""

from django.contrib.auth.hashers import check_password, make_password
from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from django.test import Client, TestCase, TransactionTestCase
from django.urls import reverse

from .models import Customer, ShopOwner


class AccountSecurityTests(TestCase):
    """Exercise real registration, login, profile, and password recovery requests."""

    @classmethod
    def setUpTestData(cls) -> None:
        """Create two accounts of each type to test cross-account attacks."""
        cls.customers = [
            Customer.objects.create_user(
                username=f"customer{index}",
                email=f"customer{index}@example.com",
                password="Original-password-1",
                security_question1="First question?",
                security_answer1=make_password("first"),
                security_question2="Second question?",
                security_answer2=make_password("second"),
            )
            for index in range(2)
        ]
        cls.owners = [
            ShopOwner.objects.create(
                name=f"owner{index}",
                store_name=f"Store {index}",
                password=make_password("Original-password-1"),
                security_question1="First question?",
                security_answer1=make_password("first"),
                security_question2="Second question?",
                security_answer2=make_password("second"),
            )
            for index in range(2)
        ]

    def verify_account(self, user_type: str, account: Customer | ShopOwner) -> None:
        """Complete the public security-question flow for a chosen account."""
        self.client = Client()
        if user_type == "customer":
            url = reverse("verify_customer_security")
            identity = {"username": account.username}
        else:
            url = reverse("verify_shop_owner_security")
            identity = {"name": account.name}
        self.client.post(url, identity)
        first = self.client.post(url, {"answer1": "first"})
        self.assertEqual(first.status_code, 200)
        self.assertNotIn("recovery_grant", self.client.session)
        response = self.client.post(url, {"answer2": "second"})
        self.assertRedirects(
            response,
            reverse("reset_password", args=[user_type, account.pk]),
            fetch_redirect_response=False,
        )

    def test_seller_signup_hashes_password_and_can_log_in(self) -> None:
        """New sellers authenticate successfully without a plaintext stored password."""
        self.client.post(
            reverse("shop_owner_signup"),
            {
                "name": "new-owner",
                "store_name": "New Store",
                "password": "Signup-password-1",
                "password2": "Signup-password-1",
                "security_question1": "First?",
                "security_answer1": "first",
                "security_question2": "Second?",
                "security_answer2": "second",
            },
        )
        owner = ShopOwner.objects.get(name="new-owner")
        self.assertNotEqual(owner.password, "Signup-password-1")
        self.assertTrue(owner.check_password("Signup-password-1"))
        response = self.client.post(
            reverse("shop_owner_login"),
            {
                "name": owner.name,
                "password": "Signup-password-1",
            },
        )
        self.assertRedirects(response, reverse("shop_owner_dashboard"))
        self.assertEqual(self.client.session["shop_owner_id"], owner.pk)

    def test_seller_wrong_password_does_not_authenticate(self) -> None:
        """An incorrect password leaves the seller unauthenticated and counts a failure."""
        owner = self.owners[0]
        response = self.client.post(
            reverse("shop_owner_login"),
            {
                "name": owner.name,
                "password": "wrong",
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertNotIn("shop_owner_id", self.client.session)
        owner.refresh_from_db()
        self.assertEqual(owner.failed_attempts, 1)

    def test_seller_profile_change_hashes_password(self) -> None:
        """Password changes retain hashing and invalidate the seller session."""
        owner = self.owners[0]
        self.client.post(
            reverse("shop_owner_login"),
            {
                "name": owner.name,
                "password": "Original-password-1",
            },
        )
        response = self.client.post(
            reverse("edit_shop_owner_profile"),
            {
                "current_password": "Original-password-1",
                "new_password": "Changed-password-2",
                "confirm_password": "Changed-password-2",
            },
        )
        self.assertRedirects(response, reverse("shop_owner_login"))
        owner.refresh_from_db()
        self.assertTrue(owner.check_password("Changed-password-2"))
        self.assertFalse(owner.check_password("Original-password-1"))
        self.assertNotIn("shop_owner_id", self.client.session)

    def test_seller_profile_rejects_wrong_current_password(self) -> None:
        """Knowing a seller session is insufficient to change their password."""
        owner = self.owners[0]
        self.client.post(
            reverse("shop_owner_login"),
            {
                "name": owner.name,
                "password": "Original-password-1",
            },
        )
        response = self.client.post(
            reverse("edit_shop_owner_profile"),
            {
                "current_password": "wrong",
                "new_password": "Changed-password-2",
                "confirm_password": "Changed-password-2",
            },
        )
        self.assertEqual(response.status_code, 200)
        owner.refresh_from_db()
        self.assertTrue(owner.check_password("Original-password-1"))

    def test_recovery_cannot_reset_another_account(self) -> None:
        """Changing the reset URL cannot change another customer's or seller's password."""
        for user_type, accounts in [
            ("customer", self.customers),
            ("shop_owner", self.owners),
        ]:
            with self.subTest(user_type=user_type):
                self.verify_account(user_type, accounts[0])
                response = self.client.post(
                    reverse("reset_password", args=[user_type, accounts[1].pk]),
                    {
                        "new_password": "Attack-password-2",
                        "confirm_password": "Attack-password-2",
                    },
                )
                self.assertRedirects(response, reverse("forgot_password"))
                accounts[1].refresh_from_db()
                self.assertTrue(accounts[1].check_password("Original-password-1"))

    def test_restarting_recovery_does_not_transfer_verification(self) -> None:
        """Starting another account's recovery cannot reuse a previous verified identity."""
        for user_type, accounts in [
            ("customer", self.customers),
            ("shop_owner", self.owners),
        ]:
            with self.subTest(user_type=user_type):
                self.verify_account(user_type, accounts[0])
                if user_type == "customer":
                    self.client.post(
                        reverse("verify_customer_security"),
                        {"username": accounts[1].username},
                    )
                else:
                    self.client.post(
                        reverse("verify_shop_owner_security"),
                        {"name": accounts[1].name},
                    )
                response = self.client.post(
                    reverse("reset_password", args=[user_type, accounts[1].pk]),
                    {
                        "new_password": "Attack-password-2",
                        "confirm_password": "Attack-password-2",
                    },
                )
                self.assertRedirects(response, reverse("forgot_password"))
                accounts[1].refresh_from_db()
                self.assertTrue(accounts[1].check_password("Original-password-1"))

    def test_both_security_answers_allow_only_verified_account_reset(self) -> None:
        """Both answers together grant one-use recovery for the correct account."""
        for user_type, accounts in [
            ("customer", self.customers),
            ("shop_owner", self.owners),
        ]:
            with self.subTest(user_type=user_type):
                account = accounts[0]
                self.verify_account(user_type, account)
                response = self.client.post(
                    reverse("reset_password", args=[user_type, account.pk]),
                    {
                        "new_password": "Recovered-password-2",
                        "confirm_password": "Recovered-password-2",
                    },
                )
                self.assertRedirects(response, reverse(f"{user_type}_login"))
                account.refresh_from_db()
                self.assertNotEqual(account.password, "Recovered-password-2")
                self.assertTrue(account.check_password("Recovered-password-2"))
                self.assertNotIn("recovery_grant", self.client.session)
                self.assertNotIn("verified_reset_user_id", self.client.session)
                replay = self.client.post(
                    reverse("reset_password", args=[user_type, account.pk]),
                    {
                        "new_password": "Replay-password-3",
                        "confirm_password": "Replay-password-3",
                    },
                )
                self.assertRedirects(replay, reverse("forgot_password"))
                account.refresh_from_db()
                self.assertTrue(account.check_password("Recovered-password-2"))

    def test_unverified_recovery_is_rejected(self) -> None:
        """Reset requests require a completed account verification."""
        for user_type, accounts in [
            ("customer", self.customers),
            ("shop_owner", self.owners),
        ]:
            with self.subTest(user_type=user_type):
                response = self.client.post(
                    reverse("reset_password", args=[user_type, accounts[0].pk]),
                    {
                        "new_password": "Attack-password-2",
                        "confirm_password": "Attack-password-2",
                    },
                )
                self.assertRedirects(response, reverse("forgot_password"))
                accounts[0].refresh_from_db()
                self.assertTrue(accounts[0].check_password("Original-password-1"))


class SellerPasswordMigrationTests(TransactionTestCase):
    """Check that existing sellers retain usable credentials after migration."""

    def test_migration_hashes_legacy_passwords_and_preserves_hashes(self) -> None:
        """Upgrade a legacy database without double-hashing existing hashed passwords."""
        previous = [
            ("accounts", "0003_customer_failed_attempts_customer_locked_until_and_more")
        ]
        latest = [("accounts", "0004_hash_shop_owner_passwords")]
        executor = MigrationExecutor(connection)
        current = executor.loader.graph.leaf_nodes()
        executor.migrate(previous)
        legacy_apps = executor.loader.project_state(previous).apps
        owner_model = legacy_apps.get_model("accounts", "ShopOwner")
        original_hash = make_password("Already-hashed-password-1")
        try:
            legacy = owner_model.objects.create(
                name="legacy", store_name="Legacy Store", password="Legacy-password-1"
            )
            hashed = owner_model.objects.create(
                name="hashed", store_name="Hashed Store", password=original_hash
            )
            MigrationExecutor(connection).migrate(latest)
            migrated = owner_model.objects.get(pk=legacy.pk)
            self.assertNotEqual(migrated.password, "Legacy-password-1")
            self.assertTrue(check_password("Legacy-password-1", migrated.password))
            self.assertEqual(
                owner_model.objects.get(pk=hashed.pk).password, original_hash
            )
        finally:
            MigrationExecutor(connection).migrate(current)
