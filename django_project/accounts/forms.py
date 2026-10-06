"""Validate registration and hash credentials before storing either account type."""

from django import forms
from django.utils.translation import gettext_lazy as _

from .models import Customer, ShopOwner
from .presentation import style_public_form
from .security import validate_new_password


class SignupForm(forms.ModelForm):
    """Common account registration validation and credential storage."""

    password = forms.CharField(max_length=128, strip=False, widget=forms.PasswordInput)
    password2 = forms.CharField(max_length=128, strip=False, widget=forms.PasswordInput)
    security_question1 = forms.CharField(max_length=255)
    security_question2 = forms.CharField(max_length=255)
    security_answer1 = forms.CharField(max_length=255)
    security_answer2 = forms.CharField(max_length=255)

    def __init__(self, *args: object, **kwargs: object) -> None:
        """Provide localized labels and accessible bound controls."""
        super().__init__(*args, **kwargs)
        style_public_form(self)

    def clean(self) -> dict:
        """Check password confirmation and strength against account information."""
        data = super().clean()
        password = data.get("password")
        if password != data.get("password2"):
            self.add_error("password2", _("رمزهای عبور مطابقت ندارند."))
        if password:
            for name in ("username", "email", "name", "store_name"):
                if name in data:
                    setattr(self.instance, name, data[name])
            validate_new_password(password, self.instance)
        return data

    def save(self, commit: bool = True) -> Customer | ShopOwner:
        """Hash both password and answers; never persist submitted plaintext."""
        account = super().save(commit=False)
        account.set_password(self.cleaned_data["password"])
        account.set_security_answers(
            self.cleaned_data["security_answer1"], self.cleaned_data["security_answer2"]
        )
        if commit:
            account.save()
        return account


class CustomerSignupForm(SignupForm):
    """Customer registration with Django's username and email validation."""

    class Meta:
        model = Customer
        fields = (
            "username",
            "email",
            "security_question1",
            "security_question2",
            "security_answer1",
            "security_answer2",
        )


class ShopOwnerSignupForm(SignupForm):
    """Seller registration with explicit public fields."""

    class Meta:
        model = ShopOwner
        fields = (
            "name",
            "store_name",
            "address",
            "phone",
            "security_question1",
            "security_question2",
            "security_answer1",
            "security_answer2",
        )

    def clean_name(self) -> str:
        """Reject a seller name that already belongs to another account."""
        name = self.cleaned_data["name"]
        if ShopOwner.objects.filter(name=name).exists():
            raise forms.ValidationError(_("این نام قبلاً ثبت شده است."))
        return name
