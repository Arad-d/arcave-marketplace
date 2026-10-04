from django.conf import settings


def currency_context(request):
    """Add currency symbol to template context."""
    return {
        'CURRENCY_SYMBOL': getattr(settings, 'CURRENCY_SYMBOL', 'ریال'),
    }
