from django.contrib import admin

from .forms import ProductForm
from .models import Cart, Comment, Order, Product, Purchase, Reply
from .services import advance_order


class AdminProductForm(ProductForm):
    """Apply the same image checks to administrator uploads."""

    class Meta(ProductForm.Meta):
        fields = "__all__"


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    form = AdminProductForm
    list_display = ["name", "shop_owner", "price", "stock", "created_at"]
    search_fields = ["name", "description"]
    list_filter = ["created_at", "shop_owner"]

    def get_queryset(self, request):
        """Lock posted edits inside Django admin's change-form transaction."""
        queryset = super().get_queryset(request)
        if (
            request.method == "POST"
            and request.resolver_match.url_name == "shop_product_change"
        ):
            return queryset.select_for_update()
        return queryset


class ReadOnlyAdmin(admin.ModelAdmin):
    """Keep cart coordination and receipt creation in the shopping service."""

    def has_add_permission(self, request) -> bool:
        """Prevent manual creation that bypasses checkout."""
        return False

    def has_change_permission(self, request, obj=None) -> bool:
        """Allow viewing, not rewriting shopping records."""
        return False

    def has_delete_permission(self, request, obj=None) -> bool:
        """Protect receipts and active carts from administrative deletion."""
        return False


@admin.register(Cart)
class CartAdmin(ReadOnlyAdmin):
    list_display = ["customer", "product", "quantity", "created_at"]
    search_fields = ["customer__username", "product__name"]
    list_filter = ["created_at"]


@admin.register(Comment)
class CommentAdmin(admin.ModelAdmin):
    list_display = ["product", "customer", "created_at"]
    search_fields = ["text"]
    list_filter = ["created_at"]


@admin.register(Reply)
class ReplyAdmin(admin.ModelAdmin):
    list_display = ["comment", "shop_owner", "created_at"]
    search_fields = ["text"]
    list_filter = ["created_at"]


@admin.register(Purchase)
class PurchaseAdmin(ReadOnlyAdmin):
    list_display = ["product", "customer", "quantity", "total_price", "created_at"]
    list_filter = ["created_at"]


@admin.register(Order)
class OrderAdmin(ReadOnlyAdmin):
    """View receipts and explicitly advance their fulfillment status."""

    list_display = ["number", "customer", "status", "total_price", "created_at"]
    list_filter = ["status", "created_at"]
    actions = ["advance_status"]

    @admin.action(description="Advance fulfillment status", permissions=["advance"])
    def advance_status(self, request, queryset) -> None:
        """Move each selected order to its next status without modifying totals."""
        for order_id in queryset.order_by("pk").values_list("pk", flat=True):
            advance_order(order_id)

    def has_advance_permission(self, request) -> bool:
        """Require the normal order-change privilege for fulfillment actions."""
        return request.user.has_perm("shop.change_order")
