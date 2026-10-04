"""Tests for recovery throttling, password policy, and authenticated sessions."""

import os
import runpy
from datetime import timedelta
from pathlib import Path
from unittest.mock import patch

from django.conf import settings
from django.contrib.auth.hashers import check_password, make_password
from django.core.exceptions import ImproperlyConfigured
from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from django.test import Client, SimpleTestCase, TestCase, TransactionTestCase
from django.urls import reverse
from django.utils import timezone

from .models import Customer, ShopOwner


class RecoverySecurityTests(TestCase):
    """Cover hostile requests and valid recovery for both account types."""

    @classmethod
    def setUpTestData(cls) -> None:
        """Create accounts with independent salted answer hashes."""
        cls.customer = Customer.objects.create_user(
            username="customer",
            email="customer@example.com",
            password="Original-password-1",
            security_question1="First?",
            security_question2="Second?",
            security_answer1=make_password("first"),
            security_answer2=make_password("second"),
        )
        cls.owner = ShopOwner.objects.create(
            name="seller",
            store_name="Store",
            password=make_password("Original-password-1"),
            security_question1="First?",
            security_question2="Second?",
            security_answer1=make_password("first"),
            security_answer2=make_password("second"),
        )

    def start(self, kind: str, client: Client) -> str:
        """Start a fresh account-specific recovery challenge."""
        url = reverse(f"verify_{kind}_security")
        identity = (
            {"username": self.customer.username}
            if kind == "customer"
            else {"name": self.owner.name}
        )
        client.post(url, identity)
        return url

    def grant(self, kind: str, client: Client) -> str:
        """Obtain a reset grant by correctly answering both questions."""
        url = self.start(kind, client)
        self.assertEqual(client.post(url, {"answer1": "  FIRST  "}).status_code, 200)
        self.assertNotIn("recovery_grant", client.session)
        response = client.post(url, {"answer2": " SECOND "})
        self.assertEqual(response.status_code, 302)
        self.assertIn("recovery_grant", client.session)
        return response.url

    def test_both_answers_are_required_in_order(self) -> None:
        """A correct second answer alone cannot bypass the first answer."""
        for kind in ("customer", "shop_owner"):
            with self.subTest(kind=kind):
                client = Client()
                url = self.start(kind, client)
                client.post(url, {"answer2": "second"})
                self.assertNotIn("recovery_grant", client.session)
                account = self.customer if kind == "customer" else self.owner
                account.refresh_from_db()
                self.assertEqual(account.recovery_failed_attempts, 1)

    def test_guess_limit_survives_new_sessions(self) -> None:
        """Five wrong answers lock recovery even across five different browsers."""
        for kind in ("customer", "shop_owner"):
            with self.subTest(kind=kind):
                for _ in range(settings.RECOVERY_MAX_ATTEMPTS):
                    client = Client()
                    url = self.start(kind, client)
                    client.post(url, {"answer1": "wrong"})
                account = self.customer if kind == "customer" else self.owner
                account.refresh_from_db()
                self.assertGreater(account.recovery_locked_until, timezone.now())
                client = Client()
                url = self.start(kind, client)
                client.post(url, {"answer1": "first"})
                client.post(url, {"answer2": "second"})
                self.assertNotIn("recovery_grant", client.session)

    def test_expired_lock_allows_recovery(self) -> None:
        """An expired account lock does not permanently prevent recovery."""
        self.owner.recovery_failed_attempts = settings.RECOVERY_MAX_ATTEMPTS
        self.owner.recovery_locked_until = timezone.now() - timedelta(seconds=1)
        self.owner.save()
        self.grant("shop_owner", Client())

    def test_challenge_expires(self) -> None:
        """Old challenge sessions cannot be completed with correct answers."""
        url = self.start("customer", self.client)
        session = self.client.session
        challenge = session["recovery_challenge"]
        challenge["started_at"] -= settings.RECOVERY_TIMEOUT_SECONDS + 1
        session["recovery_challenge"] = challenge
        session.save()
        self.client.post(url, {"answer1": "first"})
        self.assertNotIn("recovery_grant", self.client.session)
        self.assertNotIn("recovery_challenge", self.client.session)

    def test_reset_grant_expires(self) -> None:
        """A correctly signed but expired grant cannot reset a password."""
        url = self.grant("customer", self.client)
        with patch(
            "django.core.signing.time.time",
            return_value=timezone.now().timestamp() + 601,
        ):
            response = self.client.post(
                url,
                {
                    "new_password": "Changed-password-2",
                    "confirm_password": "Changed-password-2",
                },
            )
        self.assertRedirects(response, reverse("forgot_password"))
        self.customer.refresh_from_db()
        self.assertTrue(self.customer.check_password("Original-password-1"))

    def test_password_change_invalidates_other_grants(self) -> None:
        """A grant in a different session becomes invalid when the password changes."""
        first, second = Client(), Client()
        url = self.grant("shop_owner", first)
        self.grant("shop_owner", second)
        first.post(
            url,
            {
                "new_password": "Changed-password-2",
                "confirm_password": "Changed-password-2",
            },
        )
        response = second.post(
            url,
            {
                "new_password": "Replayed-password-3",
                "confirm_password": "Replayed-password-3",
            },
        )
        self.assertRedirects(response, reverse("forgot_password"))
        self.owner.refresh_from_db()
        self.assertTrue(self.owner.check_password("Changed-password-2"))

    def test_reset_rejects_weak_password_for_both_account_types(self) -> None:
        """A valid recovery grant cannot bypass the configured password policy."""
        for kind, account in (("customer", self.customer), ("shop_owner", self.owner)):
            with self.subTest(kind=kind):
                client = Client()
                url = self.grant(kind, client)
                response = client.post(
                    url, {"new_password": "123", "confirm_password": "123"}
                )
                self.assertEqual(response.status_code, 200)
                account.refresh_from_db()
                self.assertTrue(account.check_password("Original-password-1"))

    def test_blank_answers_never_verify(self) -> None:
        """Missing legacy answers cannot be used to recover an account."""
        self.customer.set_security_answers("", "")
        self.customer.save()
        self.assertFalse(self.customer.check_security_answer(1, ""))
        url = self.start("customer", self.client)
        self.client.post(url, {"answer1": ""})
        self.assertNotIn("recovery_grant", self.client.session)

    def test_tampered_grant_is_rejected(self) -> None:
        """Changing a signed grant fails closed."""
        url = self.grant("customer", self.client)
        session = self.client.session
        session["recovery_grant"] += "tampered"
        session.save()
        self.assertRedirects(self.client.get(url), reverse("forgot_password"))

    def test_locked_account_cannot_use_second_answer(self) -> None:
        """A lock imposed after the first answer also protects the second step."""
        url = self.start("shop_owner", self.client)
        self.client.post(url, {"answer1": "first"})
        self.owner.recovery_locked_until = timezone.now() + timedelta(minutes=15)
        self.owner.save()
        self.client.post(url, {"answer2": "second"})
        self.assertNotIn("recovery_grant", self.client.session)

    def test_inactive_customer_cannot_recover(self) -> None:
        """Disabled customer accounts remain disabled and cannot issue reset grants."""
        self.customer.is_active = False
        self.customer.save()
        self.start("customer", self.client)
        self.assertNotIn("recovery_challenge", self.client.session)

    def test_seller_password_change_revokes_existing_sessions(self) -> None:
        """Sessions bound to the previous seller password are rejected on the next request."""
        self.client.post(
            reverse("shop_owner_login"),
            {"name": self.owner.name, "password": "Original-password-1"},
        )
        self.assertEqual(
            self.client.get(reverse("shop_owner_dashboard")).status_code, 200
        )
        self.owner.set_password("Changed-password-2")
        self.owner.save()
        self.assertRedirects(
            self.client.get(reverse("shop_owner_dashboard")),
            reverse("shop_owner_login"),
        )
        self.assertNotIn("shop_owner_id", self.client.session)

    def test_role_switching_clears_previous_identity(self) -> None:
        """Switching roles never retains privileges from both accounts."""
        self.client.force_login(self.customer)
        self.client.post(
            reverse("shop_owner_login"),
            {"name": self.owner.name, "password": "Original-password-1"},
        )
        self.assertNotIn("_auth_user_id", self.client.session)
        self.assertIn("shop_owner_id", self.client.session)
        self.client.post(
            reverse("customer_login"),
            {"username": self.customer.username, "password": "Original-password-1"},
        )
        self.assertNotIn("shop_owner_id", self.client.session)
        self.assertEqual(int(self.client.session["_auth_user_id"]), self.customer.pk)

    def test_legacy_seller_session_requires_new_login(self) -> None:
        """A seller ID without a password-bound authentication hash is insufficient."""
        session = self.client.session
        session["shop_owner_id"] = self.owner.pk
        session.save()
        self.assertRedirects(
            self.client.get(reverse("shop_owner_dashboard")),
            reverse("shop_owner_login"),
        )

    def test_profile_rejects_weak_passwords(self) -> None:
        """Profile forms apply the same strength rules as signup and reset."""
        for kind, account in (("customer", self.customer), ("shop_owner", self.owner)):
            with self.subTest(kind=kind):
                client = Client()
                if kind == "customer":
                    client.force_login(account)
                else:
                    client.post(
                        reverse("shop_owner_login"),
                        {"name": account.name, "password": "Original-password-1"},
                    )
                response = client.post(
                    reverse(f"edit_{kind}_profile"),
                    {
                        "current_password": "Original-password-1",
                        "new_password": "123",
                        "confirm_password": "123",
                    },
                )
                self.assertEqual(response.status_code, 200)
                account.refresh_from_db()
                self.assertTrue(account.check_password("Original-password-1"))


class SignupSecurityTests(TestCase):
    """Validate all publicly submitted credential fields."""

    def signup_data(self) -> dict:
        """Return valid public account fields for either signup form."""
        return {
            "username": "newcustomer",
            "name": "newseller",
            "store_name": "A Store",
            "email": "new@example.com",
            "password": "A-strong-new-password-5",
            "password2": "A-strong-new-password-5",
            "security_question1": "First?",
            "security_question2": "Second?",
            "security_answer1": " FIRST ",
            "security_answer2": "SECOND",
        }

    def test_signup_hashes_answers_for_both_roles(self) -> None:
        """Signup persists salted hashes that accept normalized answers."""
        for kind, model in (("customer", Customer), ("shop_owner", ShopOwner)):
            with self.subTest(kind=kind):
                response = self.client.post(
                    reverse(f"{kind}_signup"), self.signup_data()
                )
                self.assertEqual(response.status_code, 302)
                account = model.objects.get()
                self.assertNotEqual(account.security_answer1, "first")
                self.assertTrue(account.check_security_answer(1, "  FIRST "))
                self.assertTrue(account.check_security_answer(2, "second"))
                self.assertFalse(account.check_security_answer(2, "incorrect"))

    def test_signup_rejects_weak_and_missing_passwords(self) -> None:
        """Both registration forms reject weak or omitted passwords."""
        for kind, model in (("customer", Customer), ("shop_owner", ShopOwner)):
            for password in ("", "123", "password", "123456789123"):
                with self.subTest(kind=kind, password=password):
                    data = self.signup_data()
                    data.update(password=password, password2=password)
                    response = self.client.post(reverse(f"{kind}_signup"), data)
                    self.assertEqual(response.status_code, 200)
                    self.assertEqual(model.objects.count(), 0)
                    self.assertTrue(response.context["form"].errors)

    def test_public_signup_cannot_grant_administrator_privileges(self) -> None:
        """Extra submitted role fields cannot elevate a newly created customer."""
        data = self.signup_data()
        data.update(is_staff="True", is_superuser="True")
        self.client.post(reverse("customer_signup"), data)
        customer = Customer.objects.get()
        self.assertFalse(customer.is_staff)
        self.assertFalse(customer.is_superuser)

    def test_signup_requires_nonempty_answers(self) -> None:
        """Whitespace-only recovery answers cannot be registered."""
        for kind, model in (("customer", Customer), ("shop_owner", ShopOwner)):
            data = self.signup_data()
            data["security_answer1"] = "   "
            response = self.client.post(reverse(f"{kind}_signup"), data)
            self.assertEqual(response.status_code, 200)
            self.assertFalse(model.objects.exists())


class SecurityAnswerMigrationTests(TransactionTestCase):
    """Verify legacy credentials are transformed rather than lost."""

    def test_legacy_answers_are_hashed_and_blank_answers_disabled(self) -> None:
        """Migrate both roles, preserving existing hashes and disabling empty answers."""
        executor = MigrationExecutor(connection)
        current = executor.loader.graph.leaf_nodes()
        previous = [("accounts", "0004_hash_shop_owner_passwords")]
        executor.migrate(previous)
        apps = executor.loader.project_state(previous).apps
        try:
            customer_model = apps.get_model("accounts", "Customer")
            owner_model = apps.get_model("accounts", "ShopOwner")
            original_hash = make_password("second")
            customer = customer_model.objects.create(
                username="legacy",
                email="legacy@example.com",
                security_answer1=" FIRST ",
                security_answer2=original_hash,
                password=make_password("original"),
            )
            owner = owner_model.objects.create(
                name="legacy",
                store_name="Legacy",
                security_answer1=" FIRST ",
                security_answer2="",
                password=make_password("original"),
            )
            MigrationExecutor(connection).migrate(current)
            migrated = Customer.objects.get(pk=customer.pk)
            self.assertTrue(migrated.check_security_answer(1, "first"))
            self.assertEqual(migrated.security_answer2, original_hash)
            migrated_owner = ShopOwner.objects.get(pk=owner.pk)
            self.assertTrue(migrated_owner.check_security_answer(1, "FIRST"))
            self.assertFalse(migrated_owner.check_security_answer(2, ""))
            self.assertFalse(check_password("", migrated_owner.security_answer2))
        finally:
            MigrationExecutor(connection).migrate(current)


class ProductionSettingsTests(SimpleTestCase):
    """Exercise production configuration without connecting to any database."""

    def load_settings(self, overrides: dict) -> dict:
        """Evaluate settings with isolated environment variables and no local .env."""
        env = {
            "DJANGO_DEBUG": "False",
            "DJANGO_SECRET_KEY": "test-only-strong-private-key-with-variety-0123456789-abcdef",
            "DJANGO_ALLOWED_HOSTS": "shop.example.com",
        }
        env.update(overrides)
        with patch.dict(os.environ, env, clear=True), patch("dotenv.load_dotenv"):
            return runpy.run_path(
                str(Path(__file__).resolve().parents[1] / "arcave/settings.py")
            )

    def test_production_enforces_https_and_secure_cookies(self) -> None:
        """Production defaults protect cookies, redirects, hosts, and framing."""
        config = self.load_settings({})
        for key in (
            "SECURE_SSL_REDIRECT",
            "SESSION_COOKIE_SECURE",
            "CSRF_COOKIE_SECURE",
            "SESSION_COOKIE_HTTPONLY",
        ):
            self.assertTrue(config[key])
        self.assertEqual(config["X_FRAME_OPTIONS"], "DENY")
        self.assertGreater(config["SECURE_HSTS_SECONDS"], 0)
        self.assertNotIn("SECURE_PROXY_SSL_HEADER", config)

    def test_production_rejects_unsafe_secrets_and_hosts(self) -> None:
        """A production process cannot start with a weak key or wildcard host."""
        for overrides in (
            {"DJANGO_SECRET_KEY": ""},
            {"DJANGO_SECRET_KEY": "django-insecure-" + "x" * 60},
            {"DJANGO_ALLOWED_HOSTS": "*"},
            {"DJANGO_ALLOWED_HOSTS": ""},
        ):
            with self.subTest(overrides=overrides), self.assertRaises(
                ImproperlyConfigured
            ):
                self.load_settings(overrides)

    def test_proxy_trust_is_explicit(self) -> None:
        """Forwarded HTTPS headers are trusted only when explicitly configured."""
        config = self.load_settings({"DJANGO_TRUST_PROXY_HTTPS": "True"})
        self.assertEqual(
            config["SECURE_PROXY_SSL_HEADER"], ("HTTP_X_FORWARDED_PROTO", "https")
        )

    def test_insecure_csrf_origin_is_rejected(self) -> None:
        """Production cannot trust an HTTP origin."""
        with self.assertRaises(ImproperlyConfigured):
            self.load_settings(
                {"DJANGO_CSRF_TRUSTED_ORIGINS": "http://shop.example.com"}
            )


class AdminCredentialTests(TestCase):
    """Administrator screens cannot bypass credential hashing."""

    def test_admin_customer_creation_hashes_password_and_requires_email(self) -> None:
        """The custom user admin creates a valid customer with a hashed password."""
        from .admin import CustomerCreationForm

        data = {
            "username": "admin-created",
            "email": "admin-created@example.com",
            "password1": "Unique-passphrase-Delta-7",
            "password2": "Unique-passphrase-Delta-7",
        }
        form = CustomerCreationForm(data)
        self.assertTrue(form.is_valid(), form.errors)
        customer = form.save()
        self.assertTrue(customer.check_password(data["password1"]))
        self.assertFalse(customer.check_security_answer(1, ""))
        data["username"] = "another-customer"
        data["email"] = ""
        self.assertFalse(CustomerCreationForm(data).is_valid())

    def test_seller_admin_cannot_edit_raw_credentials(self) -> None:
        """Seller admin exposes store details but excludes stored authentication secrets."""
        from django.contrib import admin
        from django.test import RequestFactory

        request = RequestFactory().get("/admin/")
        request.user = Customer.objects.create_superuser(
            "admin", "admin@example.com", "Unique-passphrase-Delta-7"
        )
        model_admin = admin.site._registry[ShopOwner]
        form = model_admin.get_form(request)
        for field in ("password", "security_answer1", "security_answer2"):
            self.assertNotIn(field, form.base_fields)
        self.assertFalse(model_admin.has_add_permission(request))
