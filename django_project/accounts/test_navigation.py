"""Account entry, return navigation and persistent sign-in regression tests."""

from django.conf import settings
from django.test import Client, TestCase
from django.urls import reverse

from .models import Customer, ShopOwner


class NavigationTests(TestCase):
    """Exercise the same routes a visitor uses when reopening the site."""

    def setUp(self) -> None:
        """Create a fictional account and use English for readable assertions."""
        self.customer = Customer.objects.create_user(
            username="returning",
            email="returning@example.invalid",
            password="Returning-Example-2026!",
        )
        self.client.cookies[settings.LANGUAGE_COOKIE_NAME] = "en"

    def test_guest_logo_returns_to_welcome(self) -> None:
        """The sign-in header must not send guests into the catalog."""
        response = self.client.get(reverse("customer_login"))
        self.assertContains(response, '<a href="/" class="navbar-brand">Arcave</a>')

    def test_welcome_has_no_duplicate_header_login(self) -> None:
        """Opening the welcome page shows role choices without a second sign-in link."""
        response = self.client.get(reverse("landing"))
        header = response.content.decode().split("</nav>")[0]
        self.assertNotIn(reverse("customer_login"), header)

    def test_returning_customer_skips_account_entry_pages(self) -> None:
        """A valid customer session goes straight to shopping on GET."""
        self.client.force_login(self.customer)
        for route in ("landing", "customer_login", "customer_signup"):
            with self.subTest(route=route):
                self.assertRedirects(
                    self.client.get(reverse(route)),
                    reverse("product_list"),
                    fetch_redirect_response=False,
                )

    def test_login_persists_and_new_browser_returns_to_store(self) -> None:
        """Reopening with the same device cookie restores the account, not login."""
        response = self.client.post(
            reverse("customer_login"),
            {"username": "returning", "password": "Returning-Example-2026!"},
        )
        cookie = response.cookies[settings.SESSION_COOKIE_NAME]
        self.assertEqual(int(cookie["max-age"]), 30 * 24 * 60 * 60)
        reopened = Client()
        reopened.cookies[settings.SESSION_COOKIE_NAME] = cookie.value
        self.assertRedirects(
            reopened.get(reverse("landing")),
            reverse("product_list"),
            fetch_redirect_response=False,
        )
        self.client.post(reverse("logout"))
        self.assertEqual(reopened.get(reverse("landing")).status_code, 200)

    def test_login_honors_safe_return_destination(self) -> None:
        """Sign-in returns to the protected page the customer asked for."""
        response = self.client.post(
            reverse("customer_login") + "?next=/shop/cart/",
            {"username": "returning", "password": "Returning-Example-2026!"},
        )
        self.assertRedirects(
            response, reverse("view_cart"), fetch_redirect_response=False
        )

    def test_invalid_login_retains_name_and_has_field_errors(self) -> None:
        """Missing passwords receive inline validation without losing the name."""
        response = self.client.post(
            reverse("customer_login"), {"username": "returning", "password": ""}
        )
        self.assertContains(response, 'value="returning"')
        self.assertContains(response, 'aria-invalid="true"')
        self.customer.refresh_from_db()
        self.assertEqual(self.customer.failed_attempts, 0)

    def test_external_return_destination_is_rejected(self) -> None:
        """Login must never send an account to an untrusted external URL."""
        for target in (
            "https://example.invalid/",
            "//example.invalid/",
            "/\\example.invalid/",
        ):
            with self.subTest(target=target):
                browser = Client()
                response = browser.post(
                    reverse("customer_login"),
                    {
                        "username": "returning",
                        "password": "Returning-Example-2026!",
                        "next": target,
                    },
                )
                self.assertRedirects(
                    response, reverse("product_list"), fetch_redirect_response=False
                )

    def test_signup_then_login_preserves_cart_destination(self) -> None:
        """Registration hands off to sign-in and then resumes the requested cart."""
        target = reverse("view_cart")
        response = self.client.post(
            reverse("customer_signup"),
            {
                "username": "newcustomer",
                "email": "new@example.invalid",
                "password": "A-strong-new-password-5",
                "password2": "A-strong-new-password-5",
                "security_question1": "First?",
                "security_question2": "Second?",
                "security_answer1": "first",
                "security_answer2": "second",
                "next": target,
            },
        )
        self.assertEqual(response.status_code, 302)
        page = self.client.get(response.url)
        self.assertContains(page, 'name="next" value="/shop/cart/"')
        response = self.client.post(
            response.url,
            {
                "username": "newcustomer",
                "password": "A-strong-new-password-5",
                "next": target,
            },
        )
        self.assertRedirects(response, target, fetch_redirect_response=False)

    def test_seller_reopens_dashboard_and_password_change_revokes_cookie(self) -> None:
        """Seller identity persists on the device without weakening revocation."""
        owner = ShopOwner(name="seller", store_name="Store")
        owner.set_password("Seller-Example-2026!")
        owner.save()
        response = self.client.post(
            reverse("shop_owner_login"),
            {"name": "seller", "password": "Seller-Example-2026!"},
        )
        self.assertEqual(
            int(response.cookies[settings.SESSION_COOKIE_NAME]["max-age"]),
            30 * 24 * 60 * 60,
        )
        self.assertRedirects(
            self.client.get(reverse("landing")),
            reverse("shop_owner_dashboard"),
            fetch_redirect_response=False,
        )
        owner.set_password("Changed-Seller-Example-2026!")
        owner.save()
        self.assertEqual(self.client.get(reverse("landing")).status_code, 200)

    def test_post_only_destination_returns_to_product_review(self) -> None:
        """An expired session never redirects a GET onto an add-to-cart POST route."""
        response = self.client.post(
            reverse("customer_login"),
            {
                "username": "returning",
                "password": "Returning-Example-2026!",
                "next": reverse("add_to_cart", args=[42]),
            },
        )
        self.assertRedirects(
            response,
            reverse("product_detail", args=[42]),
            fetch_redirect_response=False,
        )
