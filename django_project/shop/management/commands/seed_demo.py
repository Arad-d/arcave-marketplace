"""Populate an empty, explicitly isolated database with fictional showcase data."""

from shutil import copyfile

from accounts.models import Customer, ShopOwner
from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from shop.models import Cart, Comment, Product, Reply
from shop.services import checkout_token, place_order

PRODUCTS = [
    (
        "Orbit Headphones",
        "headphones",
        "electronics",
        2450000,
        12,
        "Over-ear headphones with soft cushions. Fictional product for the Arcave demo.",
    ),
    (
        "Focus Camera",
        "camera",
        "electronics",
        18500000,
        6,
        "A compact camera for everyday moments. Fictional specifications and pricing.",
    ),
    (
        "Studio Keyboard",
        "keyboard",
        "accessories",
        3200000,
        18,
        "A compact desk keyboard with a warm finish. Demo listing; no item will be shipped.",
    ),
    (
        "Pocket Speaker",
        "speaker",
        "electronics",
        1750000,
        9,
        "A small speaker for your workspace. Fictional product, shown for demonstration.",
    ),
    (
        "Canvas Laptop Sleeve",
        "sleeve",
        "accessories",
        850000,
        15,
        "A padded sleeve for everyday carry. A fictional accessory for this showcase.",
    ),
    (
        "Desk Lamp",
        "lamp",
        "accessories",
        1250000,
        0,
        "A warm desk light. This sold-out example demonstrates inventory states.",
    ),
]


class Command(BaseCommand):
    """Create sample accounts, products and a real service-generated order once."""

    help = "Seed an empty demo_ database using arcave.demo_settings. Never resets data."

    @transaction.atomic
    def handle(self, *args: object, **options: object) -> None:
        """Fail closed outside demo settings or when any business data exists."""
        if not getattr(settings, "DEMO_MODE", False) or not settings.DATABASES[
            "default"
        ]["NAME"].startswith("demo_"):
            raise CommandError(
                "Use arcave.demo_settings with a separate demo_ database."
            )
        if (
            Customer.objects.exists()
            or ShopOwner.objects.exists()
            or Product.objects.exists()
        ):
            raise CommandError("Demo database is not empty; nothing was changed.")
        owner = ShopOwner(
            name="demo-seller",
            store_name="Orbit Studio · Demo",
            address="Fictional demo store; no physical address",
        )
        owner.set_password("Arcave-Demo-2026!")
        owner.set_security_answers("", "")
        owner.save()
        buyer = Customer.objects.create_user(
            username="demo-buyer",
            email="buyer@example.invalid",
            password="Arcave-Demo-2026!",
        )
        media = settings.MEDIA_ROOT / "demo"
        media.mkdir(parents=True, exist_ok=True)
        products = []
        for name, artwork, category, price, stock, description in PRODUCTS:
            filename = f"{artwork}.svg"
            copyfile(settings.BASE_DIR / "static" / "demo" / filename, media / filename)
            products.append(
                Product.objects.create(
                    shop_owner=owner,
                    name=name,
                    category=category,
                    price=price,
                    stock=stock,
                    description=description,
                    image=f"demo/{filename}",
                )
            )
        Cart.objects.create(customer=buyer, product=products[0], quantity=1)
        place_order(
            buyer.pk,
            checkout_token(buyer.pk, list(buyer.cart_items.select_related("product"))),
        )
        comment = Comment.objects.create(
            customer=buyer,
            product=products[0],
            text="Fictional review: the ear cushions look comfortable and the controls are easy to reach.",
        )
        Reply.objects.create(
            comment=comment,
            shop_owner=owner,
            text="Thanks for exploring the demo. This is a sample seller reply.",
        )
        self.stdout.write(
            self.style.SUCCESS(
                "Fictional demo created. Accounts: demo-buyer / demo-seller. Password: Arcave-Demo-2026!"
            )
        )
