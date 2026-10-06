"""Shared accessible presentation for bound public forms."""

from django import forms
from django.utils.translation import gettext_lazy as _

LABELS = {
    "username": _("نام کاربری"),
    "email": _("ایمیل"),
    "password": _("رمز عبور"),
    "password2": _("تکرار رمز عبور"),
    "name": _("نام"),
    "store_name": _("نام فروشگاه"),
    "address": _("آدرس"),
    "phone": _("شماره تلفن"),
    "security_question1": _("سوال امنیتی ۱"),
    "security_question2": _("سوال امنیتی ۲"),
    "security_answer1": _("پاسخ ۱"),
    "security_answer2": _("پاسخ ۲"),
    "price": _("قیمت (ریال)"),
    "description": _("توضیحات"),
    "stock": _("تعداد موجودی"),
    "category": _("دسته‌بندی"),
    "image": _("تصویر محصول"),
    "original_stock": _("تعداد موجودی"),
}


def style_public_form(form: forms.Form) -> None:
    """Match explicit labels and Django error IDs without redisplaying secrets."""
    form.auto_id = "%s"
    for name, field in form.fields.items():
        field.label = LABELS.get(name, field.label)
        field.widget.attrs["class"] = "form-control"
        # Templates supply localized hints rather than model help text.
        field.help_text = ""
        if name == "phone":
            field.widget = forms.TextInput(
                attrs={
                    "type": "tel",
                    "class": "form-control",
                    "pattern": r"^\+[0-9]{10,15}$",
                    "autocomplete": "tel",
                }
            )
        if name.startswith("security_answer"):
            field.widget = forms.PasswordInput(
                attrs={"class": "form-control", "autocomplete": "off"}
            )
        elif name in {"password", "password2"}:
            field.widget.attrs["autocomplete"] = "new-password"
        elif name in {"username", "email"}:
            field.widget.attrs["autocomplete"] = name
        if isinstance(field.widget, forms.Textarea):
            field.widget.attrs["rows"] = 5
