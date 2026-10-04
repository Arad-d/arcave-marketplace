"""Admin screens that never expose editable plaintext credential fields."""

from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from django.contrib.auth.forms import UserCreationForm
from django.http import HttpRequest

from .models import Customer, ShopOwner


class CustomerCreationForm(UserCreationForm):
    """Require the custom customer's unique email during administrator signup."""

    class Meta(UserCreationForm.Meta):
        model = Customer
        fields = ("username", "email")


@admin.register(Customer)
class CustomerAdmin(UserAdmin):
    """Use Django's hashed password administration for customer accounts."""

    add_form = CustomerCreationForm
    add_fieldsets = (
        (
            None,
            {
                "classes": ("wide",),
                "fields": ("username", "email", "password1", "password2"),
            },
        ),
    )
    list_display = ("username", "email", "created_at")
    search_fields = ("username", "email")
    readonly_fields = ("recovery_failed_attempts", "recovery_locked_until")
    fieldsets = UserAdmin.fieldsets + (
        ("Recovery", {"fields": ("recovery_failed_attempts", "recovery_locked_until")}),
    )


@admin.register(ShopOwner)
class ShopOwnerAdmin(admin.ModelAdmin):
    """Edit store details without exposing password hashes or recovery answers."""

    list_display = ("name", "store_name", "created_at")
    search_fields = ("name", "store_name")
    list_filter = ("created_at",)
    exclude = ("password", "security_answer1", "security_answer2")
    readonly_fields = (
        "security_question1",
        "security_question2",
        "recovery_failed_attempts",
        "recovery_locked_until",
        "failed_attempts",
        "locked_until",
    )

    def has_add_permission(self, request: HttpRequest) -> bool:
        """Create sellers through the validated signup flow rather than raw model fields."""
        return False
