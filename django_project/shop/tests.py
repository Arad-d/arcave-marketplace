"""Security tests for shopping permissions, HTTP methods, CSRF, and uploads."""

from io import BytesIO
from tempfile import TemporaryDirectory
from unittest.mock import patch

from accounts.models import Customer, ShopOwner
from django.contrib.auth.hashers import make_password
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client, TestCase, override_settings
from django.urls import reverse
from PIL import Image
from PIL.PngImagePlugin import PngInfo

from .forms import ProductForm
from .models import Cart, Comment, Product, Purchase, Reply


def image_upload(
    image_format: str = "PNG", size: tuple[int, int] = (8, 8), trailing: bytes = b""
) -> SimpleUploadedFile:
    """Create a small real image for validation and upload tests."""
    output = BytesIO()
    metadata = PngInfo()
    metadata.add_text("private", "private-camera-metadata")
    Image.new("RGB", size, "red").save(output, format=image_format, pnginfo=metadata)
    return SimpleUploadedFile(
        "untrusted.html", output.getvalue() + trailing, content_type="text/html"
    )


class ShoppingSecurityTests(TestCase):
    """Ensure customers and sellers cannot cross account boundaries."""

    @classmethod
    def setUpTestData(cls) -> None:
        """Create two independent customers, sellers, products, and cart entries."""
        cls.customers = [
            Customer.objects.create_user(
                username=f"customer{index}",
                email=f"c{index}@example.com",
                password="Original-password-1",
            )
            for index in range(2)
        ]
        cls.owners = [
            ShopOwner.objects.create(
                name=f"owner{index}",
                store_name=f"Store {index}",
                password=make_password("Original-password-1"),
            )
            for index in range(2)
        ]
        cls.products = [
            Product.objects.create(
                shop_owner=owner,
                name=f"Product {index}",
                price="10.00",
                description="Description",
                stock=5,
            )
            for index, owner in enumerate(cls.owners)
        ]
        cls.carts = [
            Cart.objects.create(customer=customer, product=cls.products[0], quantity=1)
            for customer in cls.customers
        ]
        cls.comment = Comment.objects.create(
            customer=cls.customers[1], product=cls.products[1], text="A question"
        )

    def seller_client(self, index: int = 0, csrf: bool = False) -> Client:
        """Authenticate a seller through the public login form, including CSRF when requested."""
        client = Client(enforce_csrf_checks=csrf)
        client.get(reverse("shop_owner_login"))
        client.post(
            reverse("shop_owner_login"),
            {"name": self.owners[index].name, "password": "Original-password-1"},
            HTTP_X_CSRFTOKEN=client.cookies["csrftoken"].value,
        )
        self.assertIn("shop_owner_id", client.session)
        return client

    def test_customer_mutations_reject_get_without_side_effects(self) -> None:
        """Viewing a URL cannot purchase, change a cart, leave a review, or log out."""
        self.client.force_login(self.customers[0])
        for name, args in (
            ("checkout", []),
            ("remove_from_cart", [self.carts[0].pk]),
            ("update_cart", [self.carts[0].pk]),
            ("add_to_cart", [self.products[0].pk]),
            ("add_comment", [self.products[0].pk]),
            ("logout", []),
        ):
            with self.subTest(name=name):
                self.assertEqual(
                    self.client.get(reverse(name, args=args)).status_code, 405
                )
        self.assertEqual(Cart.objects.count(), 2)
        self.assertFalse(Purchase.objects.exists())
        self.products[0].refresh_from_db()
        self.assertEqual(self.products[0].stock, 5)
        self.assertIn("_auth_user_id", self.client.session)

    def test_seller_mutations_reject_get(self) -> None:
        """Product deletion and replies require explicit form submissions."""
        client = self.seller_client(1)
        self.assertEqual(
            client.get(
                reverse("delete_product", args=[self.products[1].pk])
            ).status_code,
            405,
        )
        self.assertEqual(
            client.get(reverse("reply_to_comment", args=[self.comment.pk])).status_code,
            405,
        )
        self.assertEqual(Product.objects.count(), 2)
        self.assertFalse(Reply.objects.exists())

    def test_customer_cannot_change_another_cart(self) -> None:
        """Cart identifiers never confer access to another customer's items."""
        self.client.force_login(self.customers[0])
        for name in ("update_cart", "remove_from_cart"):
            self.assertEqual(
                self.client.post(
                    reverse(name, args=[self.carts[1].pk]), {"quantity": 3}
                ).status_code,
                404,
            )
        self.carts[1].refresh_from_db()
        self.assertEqual(self.carts[1].quantity, 1)

    def test_reviews_require_a_purchase_by_the_current_customer(self) -> None:
        """Another customer's purchase does not authorize the current user to review."""
        self.client.force_login(self.customers[0])
        url = reverse("add_comment", args=[self.products[0].pk])
        Purchase.objects.create(
            customer=self.customers[1],
            product=self.products[0],
            quantity=1,
            total_price="10.00",
        )
        self.assertEqual(
            self.client.post(url, {"text": "Unpurchased review"}).status_code, 403
        )
        self.assertFalse(Comment.objects.filter(product=self.products[0]).exists())
        Purchase.objects.create(
            customer=self.customers[0],
            product=self.products[0],
            quantity=1,
            total_price="10.00",
        )
        self.assertEqual(
            self.client.post(url, {"text": "Verified review"}).status_code, 302
        )
        self.assertEqual(
            Comment.objects.get(product=self.products[0]).customer, self.customers[0]
        )

    def test_seller_cannot_manage_another_store(self) -> None:
        """Editing, deleting, viewing private comments, and replying enforce ownership."""
        client = self.seller_client()
        for name, args in (
            ("edit_product", [self.products[1].pk]),
            ("delete_product", [self.products[1].pk]),
            ("product_comments", [self.products[1].pk]),
            ("reply_to_comment", [self.comment.pk]),
        ):
            with self.subTest(name=name):
                response = client.post(
                    reverse(name, args=args),
                    {"name": "Hijacked", "text": "Unauthorized"},
                )
                self.assertEqual(response.status_code, 404)
        self.products[1].refresh_from_db()
        self.assertEqual(self.products[1].name, "Product 1")
        self.assertFalse(Reply.objects.exists())

    def test_customer_cannot_access_seller_pages(self) -> None:
        """Customer authentication does not grant seller privileges."""
        self.client.force_login(self.customers[0])
        for name, args in (
            ("shop_owner_dashboard", []),
            ("add_product", []),
            ("edit_shop_owner_profile", []),
            ("edit_product", [self.products[0].pk]),
            ("product_comments", [self.products[0].pk]),
        ):
            self.assertRedirects(
                self.client.get(reverse(name, args=args)), reverse("shop_owner_login")
            )

    def test_seller_cannot_checkout_as_customer(self) -> None:
        """A seller session alone cannot perform customer actions."""
        client = self.seller_client()
        response = client.post(
            reverse("checkout"), {"customer_id": self.customers[0].pk}
        )
        self.assertEqual(response.status_code, 302)
        self.assertFalse(Purchase.objects.exists())

    def test_customer_posts_require_csrf(self) -> None:
        """Cross-site requests cannot mutate cart data, purchase, or log out."""
        client = Client(enforce_csrf_checks=True)
        client.force_login(self.customers[0])
        for name, args in (
            ("checkout", []),
            ("remove_from_cart", [self.carts[0].pk]),
            ("update_cart", [self.carts[0].pk]),
            ("add_to_cart", [self.products[0].pk]),
            ("add_comment", [self.products[0].pk]),
            ("logout", []),
        ):
            with self.subTest(name=name):
                self.assertEqual(client.post(reverse(name, args=args)).status_code, 403)
        self.assertFalse(Purchase.objects.exists())
        self.assertEqual(Cart.objects.count(), 2)

    def test_seller_posts_require_csrf(self) -> None:
        """Seller authentication cannot bypass CSRF protection."""
        client = self.seller_client(1, csrf=True)
        for name, args in (
            ("delete_product", [self.products[1].pk]),
            ("reply_to_comment", [self.comment.pk]),
            ("edit_product", [self.products[1].pk]),
            ("add_product", []),
            ("edit_shop_owner_profile", []),
        ):
            with self.subTest(name=name):
                self.assertEqual(client.post(reverse(name, args=args)).status_code, 403)
        self.assertEqual(Product.objects.count(), 2)

    def test_rendered_actions_are_post_forms_with_csrf(self) -> None:
        """The actual shopping and seller pages still provide usable protected buttons."""
        self.client.force_login(self.customers[0])
        response = self.client.get(reverse("view_cart"))
        self.assertContains(response, f'action="{reverse("checkout")}"')
        self.assertContains(response, "csrfmiddlewaretoken")
        self.assertNotContains(response, f'href="{reverse("checkout")}"')
        seller_page = self.seller_client().get(reverse("shop_owner_dashboard"))
        self.assertContains(
            seller_page,
            f'action="{reverse("delete_product", args=[self.products[0].pk])}"',
        )
        self.assertNotContains(
            seller_page,
            f'href="{reverse("delete_product", args=[self.products[0].pk])}"',
        )

    def test_valid_csrf_checkout_and_removal_still_work(self) -> None:
        """Legitimate form submissions work after enforcing POST and CSRF."""
        client = Client(enforce_csrf_checks=True)
        client.force_login(self.customers[0])
        client.get(reverse("view_cart"))
        response = client.post(
            reverse("checkout"), HTTP_X_CSRFTOKEN=client.cookies["csrftoken"].value
        )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(Purchase.objects.filter(customer=self.customers[0]).count(), 1)
        self.assertTrue(Cart.objects.filter(pk=self.carts[1].pk).exists())

    def test_valid_csrf_seller_delete_still_works(self) -> None:
        """Sellers can delete their own product with a valid form token."""
        client = self.seller_client(csrf=True)
        response = client.post(
            reverse("delete_product", args=[self.products[0].pk]),
            HTTP_X_CSRFTOKEN=client.cookies["csrftoken"].value,
        )
        self.assertEqual(response.status_code, 302)
        self.assertFalse(Product.objects.filter(pk=self.products[0].pk).exists())

    def test_admin_image_upload_uses_the_same_validation(self) -> None:
        """The admin product form cannot bypass public upload validation."""
        from .admin import AdminProductForm

        form = AdminProductForm(
            {
                "shop_owner": self.owners[0].pk,
                "name": "Product",
                "price": "12",
                "description": "Description",
                "stock": "1",
                "category": "electronics",
            },
            {"image": SimpleUploadedFile("fake.png", b"<script>bad</script>")},
        )
        self.assertFalse(form.is_valid())
        self.assertIn("image", form.errors)

    def test_invalid_image_cannot_replace_product_or_change_details(self) -> None:
        """An invalid upload fails the whole product edit without saving other changes."""
        client = self.seller_client()
        response = client.post(
            reverse("edit_product", args=[self.products[0].pk]),
            {
                "name": "Changed",
                "price": "12",
                "description": "Changed",
                "stock": "2",
                "category": "electronics",
                "image": SimpleUploadedFile(
                    "bad.png", b"<script>alert(1)</script>", content_type="image/png"
                ),
            },
        )
        self.assertEqual(response.status_code, 200)
        self.products[0].refresh_from_db()
        self.assertEqual(self.products[0].name, "Product 0")
        self.assertFalse(self.products[0].image)

    def test_upload_saves_clean_image_to_authenticated_store(self) -> None:
        """A valid upload is sanitized and ignores a forged shop owner field."""
        client = self.seller_client()
        with TemporaryDirectory() as directory, override_settings(MEDIA_ROOT=directory):
            response = client.post(
                reverse("add_product"),
                {
                    "name": "New Product",
                    "price": "12",
                    "description": "Description",
                    "stock": "2",
                    "category": "electronics",
                    "shop_owner": self.owners[1].pk,
                    "image": image_upload(trailing=b"<script>bad</script>"),
                },
            )
            self.assertEqual(response.status_code, 302)
            product = Product.objects.get(name="New Product")
            self.assertEqual(product.shop_owner, self.owners[0])
            with product.image.open("rb") as uploaded:
                self.assertNotIn(b"<script>", uploaded.read())


class ImageValidationTests(TestCase):
    """Reject oversized, corrupt, disguised, and unsafe image uploads."""

    def form(self, upload: SimpleUploadedFile) -> ProductForm:
        """Build a product form with valid ordinary fields and a chosen image."""
        return ProductForm(
            {
                "name": "Product",
                "price": "1",
                "description": "Description",
                "stock": "1",
                "category": "electronics",
            },
            {"image": upload},
        )

    def test_allowed_images_are_reencoded_without_metadata_or_trailing_bytes(
        self,
    ) -> None:
        """Supported formats become correctly named files containing only decoded image data."""
        for image_format in ("PNG", "JPEG", "WEBP"):
            with self.subTest(image_format=image_format):
                form = self.form(
                    image_upload(image_format, trailing=b"<script>bad</script>")
                )
                self.assertTrue(form.is_valid(), form.errors)
                clean = form.cleaned_data["image"]
                self.assertNotIn("untrusted", clean.name)
                content = clean.read()
                self.assertNotIn(b"<script>", content)
                self.assertNotIn(b"private-camera-metadata", content)
                with Image.open(BytesIO(content)) as image:
                    self.assertEqual(image.format, image_format)
                    image.verify()

    def test_disguised_svg_and_corrupt_images_are_rejected(self) -> None:
        """The declared MIME type and filename do not make arbitrary bytes an image."""
        for content in (
            b'<svg onload="alert(1)"></svg>',
            b"not an image",
            image_upload().read()[:24],
        ):
            with self.subTest(content=content[:10]):
                form = self.form(
                    SimpleUploadedFile("fake.png", content, content_type="image/png")
                )
                self.assertFalse(form.is_valid())
                self.assertIn("image", form.errors)

    def test_other_image_formats_are_rejected(self) -> None:
        """Valid but unapproved raster formats are not stored."""
        self.assertFalse(self.form(image_upload("BMP")).is_valid())

    @override_settings(PRODUCT_IMAGE_MAX_BYTES=32)
    def test_file_size_is_bounded(self) -> None:
        """Oversized uploads are rejected before decoding."""
        form = self.form(SimpleUploadedFile("large.png", b"x" * 33))
        self.assertFalse(form.is_valid())
        self.assertIn("image", form.errors)

    @override_settings(PRODUCT_IMAGE_MAX_PIXELS=10)
    def test_pixel_count_is_bounded(self) -> None:
        """A small compressed file cannot bypass the decoded pixel limit."""
        self.assertFalse(self.form(image_upload(size=(4, 4))).is_valid())

    def test_dimension_limit_is_enforced(self) -> None:
        """Very wide or tall images are rejected even with few total pixels."""
        self.assertFalse(self.form(image_upload(size=(4097, 1))).is_valid())

    def test_decompression_bomb_is_rejected(self) -> None:
        """Pillow decompression warnings and errors become safe validation errors."""
        upload = image_upload()
        with patch("PIL.Image.MAX_IMAGE_PIXELS", 4):
            self.assertFalse(self.form(upload).is_valid())
