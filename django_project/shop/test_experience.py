"""Public browsing, accessible errors and isolated fictional demo setup."""

from io import StringIO
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
from unittest.mock import patch

from accounts.models import Customer, ShopOwner
from django.conf import settings
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase
from django.urls import reverse

from .models import Order, Product


class ExperienceTests(TestCase):
    """Exercise changes that affect navigation and submitted form data."""

    def test_visitors_can_browse_but_cannot_change_carts(self) -> None:
        """Opening the catalog is public; shopping still requires an account."""
        self.assertEqual(self.client.get(reverse("product_list")).status_code, 200)
        self.assertEqual(
            self.client.post(
                reverse("add_to_cart", args=[1]), {"quantity": 1}
            ).status_code,
            302,
        )

    def test_signup_retains_public_values_and_blanks_secrets(self) -> None:
        """A failed signup exposes linked field errors without echoing credentials."""
        response = self.client.post(
            reverse("customer_signup"),
            {
                "username": "demo-reader",
                "email": "invalid-email",
                "password": "Private-Secret-Value!",
                "password2": "different",
                "security_question1": "Question one",
                "security_question2": "Question two",
                "security_answer1": "secret-answer-one",
                "security_answer2": "secret-answer-two",
            },
        )
        self.assertContains(response, 'value="demo-reader"')
        self.assertContains(response, 'aria-invalid="true"')
        self.assertContains(response, 'href="#email"')
        self.assertContains(response, 'id="email_error"')
        self.assertNotContains(response, 'value="Private-Secret-Value!"')
        self.assertNotContains(response, 'value="secret-answer-one"')
        self.assertFalse(Customer.objects.exists())

    def test_invalid_product_keeps_description_category_and_price(self) -> None:
        """Seller errors retain submitted data and do not create a listing."""
        owner = ShopOwner.objects.create(
            name="seller", store_name="Store", password="!"
        )
        session = self.client.session
        session["shop_owner_id"] = owner.pk
        session["shop_owner_auth_hash"] = owner.get_session_auth_hash()
        session.save()
        response = self.client.post(
            reverse("add_product"),
            {
                "name": "Typed product",
                "price": "-2",
                "stock": "3",
                "category": "accessories",
                "description": "Keep my description",
            },
        )
        self.assertContains(response, 'value="Typed product"')
        self.assertContains(response, "Keep my description")
        self.assertContains(response, 'value="accessories" selected')
        self.assertContains(response, 'aria-describedby="price_error"')
        self.assertFalse(Product.objects.exists())


class DemoSeedTests(TestCase):
    """Seeding must never modify an ordinary or populated database."""

    def test_demo_is_opt_in(self) -> None:
        """Normal application settings refuse the seed command."""
        with self.assertRaises(CommandError):
            call_command("seed_demo", stdout=StringIO())
        self.assertFalse(Customer.objects.exists())

    def test_seed_creates_fictional_journey_once(self) -> None:
        """Use the test database while isolating the command's environment guard."""
        with TemporaryDirectory() as media:
            demo_settings = SimpleNamespace(
                DEMO_MODE=True,
                DATABASES={"default": {"NAME": "demo_test"}},
                MEDIA_ROOT=Path(media),
                BASE_DIR=settings.BASE_DIR,
            )
            with patch("shop.management.commands.seed_demo.settings", demo_settings):
                call_command("seed_demo", stdout=StringIO())
                self.assertEqual(Product.objects.count(), 6)
                self.assertEqual(Order.objects.count(), 1)
                buyer = Customer.objects.get(username="demo-buyer")
                self.assertTrue(buyer.check_password("Arcave-Demo-2026!"))
                self.assertFalse(buyer.is_staff)
                self.assertEqual(Product.objects.get(name="Orbit Headphones").stock, 11)
                with self.assertRaises(CommandError):
                    call_command("seed_demo", stdout=StringIO())
                self.assertEqual(Product.objects.count(), 6)
