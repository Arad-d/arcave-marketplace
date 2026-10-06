"""Language-aware display context shared by website templates."""

from django.http import HttpRequest
from django.utils.translation import gettext as _


def currency_context(request: HttpRequest) -> dict:
    """Translate the currency label without converting monetary amounts."""
    return {"CURRENCY_SYMBOL": _("ریال")}
