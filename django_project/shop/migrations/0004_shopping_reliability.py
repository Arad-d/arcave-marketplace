"""Keep legacy totals honest and preserve receipts independently of listings."""

from decimal import Decimal
from uuid import uuid4

import django.db.models.deletion
from django.db import migrations, models


def preserve_purchases(apps, schema_editor):
    """Each old line gets a legacy receipt; original order grouping is unknown."""
    Purchase = apps.get_model("shop", "Purchase")
    Order = apps.get_model("shop", "Order")
    alias = schema_editor.connection.alias
    for purchase in (
        Purchase.objects.using(alias).select_related("product__shop_owner").iterator()
    ):
        product = purchase.product
        order = Order.objects.using(alias).create(
            customer_id=purchase.customer_id,
            status="legacy",
            total_price=purchase.total_price,
        )
        Order.objects.using(alias).filter(pk=order.pk).update(
            created_at=purchase.created_at
        )
        Purchase.objects.using(alias).filter(pk=purchase.pk).update(
            order_id=order.pk,
            product_name=product.name,
            store_name=product.shop_owner.store_name,
            seller_id=product.shop_owner_id,
            unit_price=(
                (purchase.total_price / purchase.quantity).quantize(Decimal("0.01"))
                if purchase.total_price is not None and purchase.quantity
                else None
            ),
        )


class Migration(migrations.Migration):
    dependencies = [("shop", "0003_product_category")]
    operations = [
        migrations.CreateModel(
            name="Order",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                (
                    "number",
                    models.UUIDField(default=uuid4, unique=True, editable=False),
                ),
                (
                    "checkout_key",
                    models.UUIDField(default=uuid4, unique=True, editable=False),
                ),
                (
                    "status",
                    models.CharField(
                        max_length=20,
                        choices=[
                            ("placed", "ثبت‌شده"),
                            ("processing", "در حال آماده‌سازی"),
                            ("completed", "تکمیل‌شده"),
                            ("legacy", "خرید پیشین (وضعیت نامشخص)"),
                        ],
                        default="placed",
                    ),
                ),
                (
                    "total_price",
                    models.DecimalField(max_digits=18, decimal_places=2, null=True),
                ),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "customer",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="orders",
                        to="accounts.customer",
                    ),
                ),
            ],
            options={"ordering": ["-created_at"]},
        ),
        migrations.AlterField(
            "purchase",
            "product",
            models.ForeignKey(
                null=True,
                blank=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="purchases",
                to="shop.product",
            ),
        ),
        migrations.AlterField(
            "purchase",
            "total_price",
            models.DecimalField(max_digits=14, decimal_places=2, null=True, blank=True),
        ),
        migrations.AddField(
            "purchase",
            "order",
            models.ForeignKey(
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                related_name="items",
                to="shop.order",
            ),
        ),
        migrations.AddField(
            "purchase",
            "seller",
            models.ForeignKey(
                null=True,
                blank=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="sales",
                to="accounts.shopowner",
            ),
        ),
        migrations.AddField(
            "purchase",
            "product_name",
            models.CharField(max_length=200, default=""),
            preserve_default=False,
        ),
        migrations.AddField(
            "purchase",
            "store_name",
            models.CharField(max_length=255, default=""),
            preserve_default=False,
        ),
        migrations.AddField(
            "purchase",
            "unit_price",
            models.DecimalField(max_digits=14, decimal_places=2, null=True),
        ),
        migrations.RunPython(preserve_purchases, migrations.RunPython.noop),
        migrations.AlterField(
            "purchase",
            "order",
            models.ForeignKey(
                on_delete=django.db.models.deletion.CASCADE,
                related_name="items",
                to="shop.order",
            ),
        ),
        migrations.AddConstraint(
            "product",
            models.CheckConstraint(
                condition=models.Q(price__gt=0), name="product_positive_price"
            ),
        ),
        migrations.AddConstraint(
            "product",
            models.CheckConstraint(
                condition=models.Q(category__in=["electronics", "accessories"]),
                name="product_valid_category",
            ),
        ),
        migrations.AddConstraint(
            "cart",
            models.CheckConstraint(
                condition=models.Q(quantity__gte=1, quantity__lte=5),
                name="cart_quantity_range",
            ),
        ),
        migrations.AddConstraint(
            "purchase",
            models.CheckConstraint(
                condition=models.Q(quantity__gte=1), name="purchase_positive_quantity"
            ),
        ),
    ]
