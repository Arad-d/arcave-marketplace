"""Database-independent Persian error responses for production requests."""

from django.http import HttpRequest, HttpResponse
from django.template.loader import render_to_string

COPY = {
    400: (
        "درخواست قابل پردازش نیست",
        "لطفاً صفحه را دوباره باز کنید و اطلاعات واردشده را بررسی کنید.",
    ),
    403: (
        "دسترسی به این صفحه مجاز نیست",
        "با حساب مناسب وارد شوید و دوباره تلاش کنید.",
    ),
    404: (
        "صفحه پیدا نشد",
        "ممکن است آدرس تغییر کرده باشد یا محصول دیگر در دسترس نباشد.",
    ),
    500: (
        "مشکلی پیش آمده است",
        "لطفاً کمی بعد دوباره تلاش کنید. اگر مشکل ادامه داشت، کد پیگیری را به پشتیبانی بدهید.",
    ),
}


def error_response(
    request: HttpRequest, status: int, *, csrf: bool = False
) -> HttpResponse:
    """Render without request processors, session access or database dependencies."""
    title, message = COPY[status]
    if csrf:
        title = "فرم نیاز به تازه‌سازی دارد"
        message = "صفحه فرم را دوباره باز کنید و اطلاعات را مجدداً ارسال کنید."
    content = render_to_string(
        "errors/error.html",
        {
            "status": status,
            "title": title,
            "message": message,
            "reference": getattr(request, "error_reference", ""),
        },
    )
    response = HttpResponse(content, status=status)
    response["Cache-Control"] = "no-store"
    return response


def bad_request(request: HttpRequest, exception: Exception) -> HttpResponse:
    """Explain a bad request without exposing exception details."""
    return error_response(request, 400)


def permission_denied(request: HttpRequest, exception: Exception) -> HttpResponse:
    """Explain missing access without revealing protected resources."""
    return error_response(request, 403)


def page_not_found(request: HttpRequest, exception: Exception) -> HttpResponse:
    """Offer a way home when a page or product is missing."""
    return error_response(request, 404)


def server_error(request: HttpRequest) -> HttpResponse:
    """Remain renderable even if account or database access has failed."""
    return error_response(request, 500)


def csrf_failure(request: HttpRequest, reason: str = "") -> HttpResponse:
    """Explain an expired or invalid form without reflecting the rejection reason."""
    return error_response(request, 403, csrf=True)
