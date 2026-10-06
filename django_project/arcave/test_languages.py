"""Bilingual navigation, application messages and complete template coverage."""

import gettext
import re
from pathlib import Path

from accounts.models import Customer, ShopOwner
from django.conf import settings
from django.core.files.uploadedfile import SimpleUploadedFile
from django.template.loader import render_to_string
from django.test import Client, RequestFactory, TestCase, override_settings
from django.urls import reverse
from django.utils import translation
from shop.forms import ProductForm
from shop.models import Cart, Comment, Order, Product, Purchase


class LanguageTests(TestCase):
    """The language preference translates UI while preserving data and shopping state."""

    def setUp(self) -> None:
        """Create representative English demo content for both account types."""
        self.customer = Customer.objects.create_user(
            username="reader", email="reader@example.com"
        )
        self.owner = ShopOwner.objects.create(
            name="seller", store_name="Local store", password="!"
        )
        self.product = Product.objects.create(
            shop_owner=self.owner,
            name="Camera",
            description="Example product",
            price="12.50",
            stock=5,
        )
        self.order = Order.objects.create(customer=self.customer, total_price="12.50")
        Purchase.objects.create(
            order=self.order,
            customer=self.customer,
            product=self.product,
            seller=self.owner,
            product_name="Camera",
            store_name="Local store",
            unit_price="12.50",
            total_price="12.50",
        )
        self.comment = Comment.objects.create(
            product=self.product, customer=self.customer, text="A review"
        )

    def tearDown(self) -> None:
        """Prevent language activation from leaking into other test classes."""
        translation.deactivate()
        super().tearDown()

    def english_client(self, seller: bool = False) -> Client:
        """Create a browser with a saved English preference and optional seller session."""
        client = Client()
        client.cookies[settings.LANGUAGE_COOKIE_NAME] = "en"
        if seller:
            session = client.session
            session["shop_owner_id"] = self.owner.pk
            session["shop_owner_auth_hash"] = self.owner.get_session_auth_hash()
            session.save()
        return client

    def assert_english(self, response) -> None:
        """Assert the page is English apart from the native-name language button."""
        self.assertEqual(response.status_code, 200)
        html = response.content.decode()
        self.assertIn('lang="en" dir="ltr"', html)
        html = re.sub(
            r'<form[^>]*class="language-switch inline-action".*?</form>',
            "",
            html,
            flags=re.S,
        )
        self.assertIsNone(re.search(r"[\u0600-\u06ff]", html), html)

    def test_public_pages_are_fully_english(self) -> None:
        """Landing, sign-in, sign-up, recovery and store pages translate their text."""
        client = self.english_client()
        for name, args in (
            ("landing", []),
            ("customer_login", []),
            ("shop_owner_login", []),
            ("customer_signup", []),
            ("shop_owner_signup", []),
            ("forgot_password", []),
            ("verify_customer_security", []),
            ("verify_shop_owner_security", []),
            ("product_detail", [self.product.pk]),
            ("shop_profile", [self.owner.pk]),
        ):
            with self.subTest(page=name):
                self.assert_english(client.get(reverse(name, args=args)))

    def test_customer_pages_and_header_switch(self) -> None:
        """English applies to nonempty shopping pages and the switch follows the cart."""
        client = self.english_client()
        client.force_login(self.customer)
        Cart.objects.create(customer=self.customer, product=self.product, quantity=2)
        for name, args in (
            ("product_list", []),
            ("customer_dashboard", []),
            ("view_cart", []),
            ("edit_customer_profile", []),
            ("order_detail", [self.order.number]),
        ):
            with self.subTest(page=name):
                response = client.get(reverse(name, args=args))
                self.assert_english(response)
        html = client.get(reverse("view_cart")).content.decode()
        self.assertRegex(
            html,
            r'(?s)href="/shop/cart/">Cart</a></li>\s*<li>\s*.*?class="language-switch inline-action"',
        )
        self.assertIn(
            "Placed",
            (
                html
                if "Placed" in html
                else client.get(
                    reverse("order_detail", args=[self.order.number])
                ).content.decode()
            ),
        )

    def test_seller_pages_are_fully_english(self) -> None:
        """Seller forms, sales history, comments and profile have translated labels."""
        client = self.english_client(seller=True)
        for name, args in (
            ("shop_owner_dashboard", []),
            ("add_product", []),
            ("edit_product", [self.product.pk]),
            ("product_comments", [self.product.pk]),
            ("edit_shop_owner_profile", []),
        ):
            with self.subTest(page=name):
                self.assert_english(client.get(reverse(name, args=args)))

    def test_switch_persists_and_preserves_cart_account_and_search(self) -> None:
        """Switch language using the real CSRF-protected form without losing state."""
        client = Client(enforce_csrf_checks=True)
        client.force_login(self.customer)
        item = Cart.objects.create(customer=self.customer, product=self.product)
        target = reverse("product_list") + "?q=Camera&category=electronics"
        client.get(target)
        url = reverse("set_language")
        self.assertEqual(
            client.post(url, {"language": "en", "next": target}).status_code, 403
        )
        for language, direction, title in (
            ("en", "ltr", "Search results"),
            ("fa", "rtl", "نتایج جستجو"),
        ):
            response = client.post(
                url,
                {"language": language, "next": target},
                HTTP_X_CSRFTOKEN=client.cookies["csrftoken"].value,
            )
            self.assertEqual(response["Location"], target)
            self.assertEqual(
                client.cookies[settings.LANGUAGE_COOKIE_NAME].value, language
            )
            page = client.get(target)
            self.assertContains(page, f'lang="{language}" dir="{direction}"')
            self.assertContains(page, title)
            self.assertEqual(int(client.session["_auth_user_id"]), self.customer.pk)
            self.assertTrue(Cart.objects.filter(pk=item.pk).exists())

    def test_language_redirect_cannot_leave_the_site(self) -> None:
        """Django's language endpoint rejects external next URLs and unknown languages."""
        client = self.english_client()
        response = client.post(
            reverse("set_language"),
            {"language": "fa", "next": "https://untrusted.example/"},
        )
        self.assertEqual(response["Location"], "/")
        client.post(reverse("set_language"), {"language": "unknown", "next": "/"})
        self.assertEqual(client.cookies[settings.LANGUAGE_COOKIE_NAME].value, "fa")

    def test_validation_messages_and_categories_translate_at_request_time(self) -> None:
        """Forms and model choice labels are not frozen to the startup language."""
        for language, category, message in (
            ("en", "Electronics", "The image file is invalid."),
            ("fa", "محصولات الکترونیک", "فایل تصویر معتبر نیست."),
        ):
            with translation.override(language):
                self.assertEqual(self.product.get_category_display(), category)
                form = ProductForm(
                    {
                        "name": "Test",
                        "price": "1",
                        "stock": 1,
                        "description": "Test",
                        "category": "electronics",
                    },
                    {"image": SimpleUploadedFile("bad.png", b"not an image")},
                )
                self.assertFalse(form.is_valid())
                self.assertIn(message, form.errors["image"])
        client = self.english_client()
        client.force_login(self.customer)
        response = client.post(
            reverse("add_to_cart", args=[self.product.pk]), {"quantity": 0}, follow=True
        )
        self.assertContains(response, "Enter a whole number between 1 and 5.")

    @override_settings(DEBUG=False, SECURE_SSL_REDIRECT=False)
    def test_english_error_pages_and_admin_login(self) -> None:
        """Standalone error rendering and Django admin use the selected language too."""
        client = self.english_client()
        response = client.get("/not-a-page/")
        self.assertContains(response, "Page not found", status_code=404)
        self.assertContains(response, 'lang="en" dir="ltr"', status_code=404)
        response = client.get(reverse("admin:login"))
        self.assertContains(response, "Username")
        self.assertContains(response, 'name="language" value="fa"')

    def test_recovery_templates_render_all_stages_in_english(self) -> None:
        """Later recovery stages and reset forms translate even before a live grant."""
        request = RequestFactory().get("/")
        request.session = {}
        with translation.override("en"):
            for template in (
                "verify_customer_security",
                "verify_shop_owner_security",
                "reset_password",
            ):
                for step in (1, 2, 3):
                    html = render_to_string(
                        f"accounts/{template}.html",
                        {
                            "step": step,
                            "question": "Test question",
                            "user_type": "customer",
                        },
                        request=request,
                    )
                    html = re.sub(
                        r'<form[^>]*class="language-switch inline-action".*?</form>',
                        "",
                        html,
                        flags=re.S,
                    )
                    self.assertIsNone(re.search(r"[\u0600-\u06ff]", html), template)

    def test_compiled_catalog_has_no_untranslated_persian_messages(self) -> None:
        """Catch missing translations in the runtime catalog, including hidden branches."""
        path = Path(settings.LOCALE_PATHS[0]) / "en/LC_MESSAGES/django.mo"
        with path.open("rb") as catalog_file:
            catalog = gettext.GNUTranslations(catalog_file)
        for key, value in catalog._catalog.items():
            if key:
                self.assertFalse(re.search(r"[\u0600-\u06ff]", value), key)
