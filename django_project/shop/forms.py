"""Validate product fields and sanitize uploaded raster images."""

import warnings
from decimal import Decimal
from io import BytesIO
from uuid import uuid4

from django import forms
from django.conf import settings
from django.core.files.base import ContentFile
from django.core.files.uploadedfile import UploadedFile
from django.utils.translation import gettext_lazy as _
from PIL import Image, UnidentifiedImageError

from .models import Product


class ProductForm(forms.ModelForm):
    """Limit product updates to public fields and bounded, decoded images."""

    original_stock = forms.IntegerField(required=False, widget=forms.HiddenInput)
    image = forms.FileField(required=False)
    price = forms.DecimalField(
        min_value=Decimal("0.01"), max_digits=10, decimal_places=2
    )

    class Meta:
        model = Product
        fields = ("name", "price", "description", "stock", "category", "image")

    def __init__(self, *args: object, **kwargs: object) -> None:
        """Require the stock value seen when opening an existing product."""
        super().__init__(*args, **kwargs)
        if self.instance.pk:
            self.fields["original_stock"].required = True
            self.initial["original_stock"] = self.instance.stock

    def clean(self) -> dict:
        """Reject stale inventory edits instead of restoring already sold units."""
        cleaned = super().clean()
        if self.instance.pk and cleaned.get("original_stock") != self.instance.stock:
            raise forms.ValidationError(
                _("موجودی تغییر کرده است. صفحه را تازه کنید و دوباره تلاش کنید.")
            )
        return cleaned

    def clean_image(self) -> object:
        """Decode and re-encode JPEG, PNG, or WebP, discarding filenames and metadata."""
        upload = self.cleaned_data.get("image")
        if not isinstance(upload, UploadedFile):
            return upload
        if upload.size > settings.PRODUCT_IMAGE_MAX_BYTES:
            raise forms.ValidationError(_("حجم تصویر باید حداکثر ۵ مگابایت باشد."))
        try:
            with warnings.catch_warnings():
                warnings.simplefilter("error", Image.DecompressionBombWarning)
                upload.seek(0)
                with Image.open(upload) as image:
                    image_format = image.format
                    if image_format not in {"JPEG", "PNG", "WEBP"}:
                        raise forms.ValidationError(
                            _("فقط تصاویر JPG، PNG و WebP مجاز هستند.")
                        )
                    if (
                        image.width > 4096
                        or image.height > 4096
                        or image.width * image.height
                        > settings.PRODUCT_IMAGE_MAX_PIXELS
                    ):
                        raise forms.ValidationError(
                            _("ابعاد تصویر بیش از حد مجاز است (حداکثر ۴۰۹۶ پیکسل).")
                        )
                    image.verify()
                upload.seek(0)
                with Image.open(upload) as image:
                    image.load()
                    # Copy decoded pixels into a new image to discard all source metadata.
                    mode = "RGB" if image_format == "JPEG" else "RGBA"
                    converted = image.convert(mode)
                    clean = Image.new(mode, image.size)
                    clean.paste(converted)
                    output = BytesIO()
                    clean.save(output, format=image_format)
            if output.tell() > settings.PRODUCT_IMAGE_MAX_BYTES:
                raise forms.ValidationError(
                    _("حجم تصویر پردازش‌شده بیش از حد مجاز است.")
                )
        except (
            UnidentifiedImageError,
            OSError,
            ValueError,
            SyntaxError,
            Image.DecompressionBombError,
            Image.DecompressionBombWarning,
        ) as error:
            raise forms.ValidationError(_("فایل تصویر معتبر نیست.")) from error
        suffix = {"JPEG": "jpg", "PNG": "png", "WEBP": "webp"}[image_format]
        return ContentFile(output.getvalue(), name=f"{uuid4().hex}.{suffix}")


class QuantityForm(forms.Form):
    """Accept explicit, bounded whole-unit quantities."""

    quantity = forms.IntegerField(min_value=1, max_value=5)


class MessageForm(forms.Form):
    """Reject empty or excessively long customer and seller messages."""

    text = forms.CharField(max_length=2000, strip=True)
