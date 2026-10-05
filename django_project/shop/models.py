from uuid import uuid4

from accounts.models import Customer, ShopOwner
from django.db import models


class Product(models.Model):
    """Product/commodity model with inventory tracking."""

    CATEGORY_CHOICES = [
        ("electronics", "محصولات الکترونیک"),
        ("accessories", "لوازم جانبی الکترونیک"),
    ]

    shop_owner = models.ForeignKey(
        ShopOwner, on_delete=models.CASCADE, related_name="products"
    )
    name = models.CharField(max_length=200)
    price = models.DecimalField(max_digits=10, decimal_places=2)
    description = models.TextField()
    image = models.ImageField(upload_to="products/", blank=True, null=True)
    stock = models.PositiveIntegerField(
        default=0, help_text="Number of units available"
    )
    category = models.CharField(
        max_length=20, choices=CATEGORY_CHOICES, default="electronics"
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.CheckConstraint(
                condition=models.Q(price__gt=0), name="product_positive_price"
            ),
            models.CheckConstraint(
                condition=models.Q(category__in=["electronics", "accessories"]),
                name="product_valid_category",
            ),
        ]
        db_table = "products"
        ordering = ["-created_at"]

    def __str__(self):
        return self.name

    def is_in_stock(self):
        return self.stock > 0

    def has_enough_stock(self, quantity):
        return self.stock >= quantity


class Cart(models.Model):
    """Shopping cart for customers."""

    customer = models.ForeignKey(
        Customer, on_delete=models.CASCADE, related_name="cart_items"
    )
    product = models.ForeignKey(
        Product, on_delete=models.CASCADE, related_name="cart_entries"
    )
    quantity = models.PositiveIntegerField(default=1)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.CheckConstraint(
                condition=models.Q(quantity__gte=1, quantity__lte=5),
                name="cart_quantity_range",
            )
        ]
        db_table = "cart"
        unique_together = ["customer", "product"]
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.customer.username} - {self.product.name} x{self.quantity}"

    def get_total_price(self):
        return self.product.price * self.quantity


class Comment(models.Model):
    """Customer comments on products."""

    product = models.ForeignKey(
        Product, on_delete=models.CASCADE, related_name="comments"
    )
    customer = models.ForeignKey(
        Customer, on_delete=models.CASCADE, related_name="comments"
    )
    text = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "comments"
        ordering = ["-created_at"]

    def __str__(self):
        return f"Comment by {self.customer.username} on {self.product.name}"

    def has_reply(self):
        return hasattr(self, "reply")


class Reply(models.Model):
    """Shop owner replies to comments."""

    comment = models.OneToOneField(
        Comment, on_delete=models.CASCADE, related_name="reply"
    )
    shop_owner = models.ForeignKey(
        ShopOwner, on_delete=models.CASCADE, related_name="replies"
    )
    text = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "replies"
        ordering = ["-created_at"]

    def __str__(self):
        return f"Reply by {self.shop_owner.store_name}"


class Order(models.Model):
    """A checkout receipt; placed does not imply that payment was collected."""

    class Status(models.TextChoices):
        PLACED = "placed", "ثبت‌شده"
        PROCESSING = "processing", "در حال آماده‌سازی"
        COMPLETED = "completed", "تکمیل‌شده"
        LEGACY = "legacy", "خرید پیشین (وضعیت نامشخص)"

    number = models.UUIDField(default=uuid4, unique=True, editable=False)
    checkout_key = models.UUIDField(default=uuid4, unique=True, editable=False)
    customer = models.ForeignKey(
        Customer, on_delete=models.CASCADE, related_name="orders"
    )
    status = models.CharField(
        max_length=20, choices=Status.choices, default=Status.PLACED
    )
    total_price = models.DecimalField(max_digits=18, decimal_places=2, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self) -> str:
        """Return the unique public receipt number."""
        return f"ARC-{self.number}"


class Purchase(models.Model):
    """Immutable receipt line with snapshots independent of the live listing."""

    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name="items")
    product = models.ForeignKey(
        Product,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="purchases",
    )
    seller = models.ForeignKey(
        ShopOwner,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="sales",
    )
    product_name = models.CharField(max_length=200)
    store_name = models.CharField(max_length=255)
    unit_price = models.DecimalField(max_digits=14, decimal_places=2, null=True)
    customer = models.ForeignKey(
        Customer, on_delete=models.CASCADE, related_name="purchases"
    )
    quantity = models.PositiveIntegerField(default=1)
    total_price = models.DecimalField(
        max_digits=14, decimal_places=2, null=True, blank=True
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "purchases"
        ordering = ["-created_at"]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(quantity__gte=1), name="purchase_positive_quantity"
            )
        ]

    def __str__(self) -> str:
        """Describe the purchase even after its listing has been deleted."""
        return f"{self.customer.username} bought {self.quantity}x {self.product_name}"
