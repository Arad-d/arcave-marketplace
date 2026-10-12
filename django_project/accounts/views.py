from datetime import timedelta
from urllib.parse import unquote, urlencode, urlsplit

from django.conf import settings
from django.contrib import messages
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.http import HttpRequest, HttpResponse
from django.middleware.csrf import rotate_token
from django.shortcuts import redirect, render
from django.urls import Resolver404, resolve, reverse
from django.utils import timezone
from django.utils.http import url_has_allowed_host_and_scheme
from django.utils.translation import gettext_lazy as _
from django.views.decorators.http import require_POST

from .forms import (
    CustomerSignInForm,
    CustomerSignupForm,
    SellerSignInForm,
    ShopOwnerSignupForm,
)
from .middleware import shop_owner_required
from .models import Customer, ShopOwner
from .recovery import reset_password as reset_password
from .recovery import verify_security
from .security import password_is_valid


# Helper functions for account lockout
def is_account_locked(user):
    """Check if account is currently locked."""
    if user.locked_until and timezone.now() < user.locked_until:
        remaining = int((user.locked_until - timezone.now()).total_seconds())
        return True, remaining
    return False, 0


def lock_account(user):
    """Lock account for 5 minutes."""
    user.locked_until = timezone.now() + timedelta(minutes=5)
    user.failed_attempts = 0
    user.save(update_fields=["failed_attempts", "locked_until"])


def record_failed_attempt(user: Customer | ShopOwner) -> None:
    """Count failed logins under a row lock so parallel requests cannot lose failures."""
    with transaction.atomic():
        current = type(user).objects.select_for_update().get(pk=user.pk)
        if current.locked_until and current.locked_until <= timezone.now():
            current.failed_attempts = 0
            current.locked_until = None
        current.failed_attempts += 1
        if current.failed_attempts >= 2:
            lock_account(current)
        else:
            current.save(update_fields=["failed_attempts", "locked_until"])
        user.failed_attempts = current.failed_attempts
        user.locked_until = current.locked_until


def clear_failed_attempts(user):
    """Clear failed attempts after successful login."""
    user.failed_attempts = 0
    user.locked_until = None
    user.save(update_fields=["failed_attempts", "locked_until"])


def account_destination(request: HttpRequest) -> str | None:
    """Choose the entry destination from a validated existing identity."""
    if request.user.is_authenticated:
        return "product_list"
    if request.shop_owner is not None:
        return "shop_owner_dashboard"
    return None


def safe_next(request: HttpRequest) -> str:
    """Preserve a same-site return path without allowing external redirects."""
    target = request.POST.get("next", request.GET.get("next", ""))
    if target.startswith("/") and url_has_allowed_host_and_scheme(
        target, allowed_hosts={request.get_host()}, require_https=request.is_secure()
    ):
        try:
            match = resolve(unquote(urlsplit(target).path))
        except Resolver404:
            return ""
        # A redirected POST cannot be replayed: return to its review page instead.
        if match.url_name in {"add_to_cart", "add_comment"}:
            return reverse("product_detail", args=[match.kwargs["pk"]])
        if match.url_name in {"update_cart", "remove_from_cart", "checkout"}:
            return reverse("view_cart")
        if match.url_name in {
            "product_list",
            "product_detail",
            "shop_profile",
            "view_cart",
            "customer_dashboard",
            "order_detail",
            "edit_customer_profile",
            "shop_owner_dashboard",
            "add_product",
            "edit_product",
            "product_comments",
            "edit_shop_owner_profile",
        }:
            return target
    return ""


def landing(request: HttpRequest) -> HttpResponse:
    """Welcome guests and resume the correct workspace for returning accounts."""
    destination = account_destination(request)
    if destination:
        return redirect(safe_next(request) or destination)
    return render(request, "accounts/landing.html", {"next": safe_next(request)})


def customer_signup(request: HttpRequest) -> HttpResponse:
    """Register an account after validating and hashing all credentials."""
    destination = account_destination(request)
    if request.method == "GET" and destination:
        return redirect(destination)
    form = CustomerSignupForm(request.POST if request.method == "POST" else None)
    if request.method == "POST":
        if form.is_valid():
            form.save()
            messages.success(request, _("حساب با موفقیت ایجاد شد. لطفاً وارد شوید."))
            target = reverse("customer_login")
            if safe_next(request):
                target += "?" + urlencode({"next": safe_next(request)})
            return redirect(target)
    return render(
        request,
        "accounts/customer_signup.html",
        {"form": form, "next": safe_next(request)},
    )


def customer_login(request: HttpRequest) -> HttpResponse:
    """Validate sign-in and resume a saved destination with a persistent session."""
    destination = account_destination(request)
    if request.method == "GET" and request.user.is_authenticated:
        return redirect(safe_next(request) or destination)
    form = CustomerSignInForm(request.POST if request.method == "POST" else None)
    context = {"form": form, "next": safe_next(request)}
    if request.method == "POST" and not form.is_valid():
        return render(request, "accounts/customer_login.html", context)
    if request.method == "POST":
        username = form.cleaned_data["username"]
        password = form.cleaned_data["password"]

        # Check if account exists and is locked
        try:
            customer = Customer.objects.get(username=username)
            locked, remaining = is_account_locked(customer)
            if locked:
                minutes = remaining // 60
                seconds = remaining % 60
                messages.error(
                    request,
                    _(
                        "حساب کاربری قفل شده است. لطفاً پس از %(value0)s:%(value1)s دوباره تلاش کنید."
                    )
                    % {"value0": f"{minutes}", "value1": f"{seconds:02d}"},
                )
                return render(request, "accounts/customer_login.html", context)
        except Customer.DoesNotExist:
            pass

        user = authenticate(request, username=username, password=password)

        if user is not None:
            # Clear failed attempts on successful login
            try:
                customer = Customer.objects.get(username=username)
                clear_failed_attempts(customer)
            except Customer.DoesNotExist:
                pass
            logout(request)
            login(request, user)
            request.session.set_expiry(settings.ACCOUNT_SESSION_AGE)
            return redirect(safe_next(request) or "product_list")
        else:
            # Record failed attempt
            try:
                customer = Customer.objects.get(username=username)
                record_failed_attempt(customer)
                locked, remaining = is_account_locked(customer)
                if locked:
                    minutes = remaining // 60
                    seconds = remaining % 60
                    messages.error(
                        request,
                        _(
                            "تلاش‌های ناموفق زیاد. حساب کاربری برای %(value0)s:%(value1)s قفل شده است."
                        )
                        % {"value0": f"{minutes}", "value1": f"{seconds:02d}"},
                    )
                else:
                    messages.error(request, _("نام کاربری یا رمز عبور اشتباه است."))
            except Customer.DoesNotExist:
                messages.error(request, _("نام کاربری یا رمز عبور اشتباه است."))

    return render(request, "accounts/customer_login.html", context)


def shop_owner_signup(request: HttpRequest) -> HttpResponse:
    """Register an account after validating and hashing all credentials."""
    destination = account_destination(request)
    if request.method == "GET" and destination:
        return redirect(destination)
    form = ShopOwnerSignupForm(request.POST if request.method == "POST" else None)
    if request.method == "POST":
        if form.is_valid():
            form.save()
            messages.success(request, _("حساب با موفقیت ایجاد شد. لطفاً وارد شوید."))
            target = reverse("shop_owner_login")
            if safe_next(request):
                target += "?" + urlencode({"next": safe_next(request)})
            return redirect(target)
    return render(
        request,
        "accounts/shop_owner_signup.html",
        {"form": form, "next": safe_next(request)},
    )


def shop_owner_login(request: HttpRequest) -> HttpResponse:
    """Validate sign-in and resume a saved destination with a persistent session."""
    destination = account_destination(request)
    if request.method == "GET" and request.shop_owner is not None:
        return redirect(safe_next(request) or destination)
    form = SellerSignInForm(request.POST if request.method == "POST" else None)
    context = {"form": form, "next": safe_next(request)}
    if request.method == "POST" and not form.is_valid():
        return render(request, "accounts/shop_owner_login.html", context)
    if request.method == "POST":
        name = form.cleaned_data["name"]
        password = form.cleaned_data["password"]

        # Check if account exists and is locked
        try:
            shop_owner = ShopOwner.objects.get(name=name)
            locked, remaining = is_account_locked(shop_owner)
            if locked:
                minutes = remaining // 60
                seconds = remaining % 60
                messages.error(
                    request,
                    _(
                        "حساب کاربری قفل شده است. لطفاً پس از %(value0)s:%(value1)s دوباره تلاش کنید."
                    )
                    % {"value0": f"{minutes}", "value1": f"{seconds:02d}"},
                )
                return render(request, "accounts/shop_owner_login.html", context)
        except ShopOwner.DoesNotExist:
            pass

        try:
            shop_owner = ShopOwner.objects.get(name=name)
            if not shop_owner.check_password(password):
                raise ShopOwner.DoesNotExist
            # Clear failed attempts on successful login
            clear_failed_attempts(shop_owner)
            # Store shop owner ID in session
            logout(request)
            rotate_token(request)
            request.session["shop_owner_auth_hash"] = shop_owner.get_session_auth_hash()
            request.session["shop_owner_id"] = shop_owner.id
            request.session["shop_owner_name"] = shop_owner.name
            request.session["shop_owner_store"] = shop_owner.store_name
            request.session.set_expiry(settings.ACCOUNT_SESSION_AGE)
            return redirect(safe_next(request) or "shop_owner_dashboard")
        except ShopOwner.DoesNotExist:
            # Record failed attempt
            try:
                shop_owner = ShopOwner.objects.get(name=name)
                record_failed_attempt(shop_owner)
                locked, remaining = is_account_locked(shop_owner)
                if locked:
                    minutes = remaining // 60
                    seconds = remaining % 60
                    messages.error(
                        request,
                        _(
                            "تلاش‌های ناموفق زیاد. حساب کاربری برای %(value0)s:%(value1)s قفل شده است."
                        )
                        % {"value0": f"{minutes}", "value1": f"{seconds:02d}"},
                    )
                else:
                    messages.error(request, _("نام یا رمز عبور اشتباه است."))
            except ShopOwner.DoesNotExist:
                messages.error(request, _("نام یا رمز عبور اشتباه است."))

    return render(request, "accounts/shop_owner_login.html", context)


@require_POST
def logout_view(request):
    """Logout view for both customer and shop owner."""
    logout(request)
    # Clear shop owner session if exists
    if "shop_owner_id" in request.session:
        del request.session["shop_owner_id"]
        del request.session["shop_owner_name"]
        del request.session["shop_owner_store"]
    return redirect("landing")


@login_required
def edit_customer_profile(request):
    """Edit customer profile - username cannot be changed."""
    customer = request.user

    if request.method == "POST":
        email = request.POST.get("email")
        current_password = request.POST.get("current_password")
        new_password = request.POST.get("new_password")
        confirm_password = request.POST.get("confirm_password")

        # Update email
        if email and email != customer.email:
            if Customer.objects.filter(email=email).exclude(pk=customer.pk).exists():
                messages.error(request, _("این ایمیل قبلاً ثبت شده است."))
                return render(
                    request,
                    "accounts/edit_customer_profile.html",
                    {"customer": customer},
                )
            customer.email = email

        # Update password if provided
        if current_password or new_password or confirm_password:
            if not customer.check_password(current_password):
                messages.error(request, _("رمز عبور فعلی اشتباه است."))
                return render(
                    request,
                    "accounts/edit_customer_profile.html",
                    {"customer": customer},
                )

            if new_password != confirm_password:
                messages.error(request, _("رمزهای عبور جدید مطابقت ندارند."))
                return render(
                    request,
                    "accounts/edit_customer_profile.html",
                    {"customer": customer},
                )

            if not password_is_valid(request, new_password, customer):
                return render(
                    request,
                    "accounts/edit_customer_profile.html",
                    {"customer": customer},
                )

            customer.set_password(new_password)
            messages.success(
                request, _("رمز عبور با موفقیت به‌روزرسانی شد! لطفاً دوباره وارد شوید.")
            )
            customer.save()
            logout(request)
            return redirect("customer_login")

        customer.save()
        messages.success(request, _("پروفایل با موفقیت به‌روزرسانی شد!"))
        return redirect("customer_dashboard")

    return render(
        request, "accounts/edit_customer_profile.html", {"customer": customer}
    )


@shop_owner_required
def edit_shop_owner_profile(request):
    """Edit shop owner profile - name (username) cannot be changed."""
    shop_owner_id = request.session.get("shop_owner_id")

    if not shop_owner_id:
        messages.error(request, _("لطفاً به عنوان فروشنده وارد شوید."))
        return redirect("shop_owner_login")

    try:
        shop_owner = ShopOwner.objects.get(id=shop_owner_id)
    except ShopOwner.DoesNotExist:
        messages.error(request, _("فروشنده یافت نشد."))
        return redirect("shop_owner_login")

    if request.method == "POST":
        store_name = request.POST.get("store_name")
        address = request.POST.get("address")
        phone = request.POST.get("phone")
        current_password = request.POST.get("current_password")
        new_password = request.POST.get("new_password")
        confirm_password = request.POST.get("confirm_password")

        # Update profile info
        if store_name:
            shop_owner.store_name = store_name
        shop_owner.address = address
        shop_owner.phone = phone

        # Update password if provided
        if current_password or new_password or confirm_password:
            if not shop_owner.check_password(current_password):
                messages.error(request, _("رمز عبور فعلی اشتباه است."))
                return render(
                    request,
                    "accounts/edit_shop_owner_profile.html",
                    {"shop_owner": shop_owner},
                )

            if new_password != confirm_password:
                messages.error(request, _("رمزهای عبور جدید مطابقت ندارند."))
                return render(
                    request,
                    "accounts/edit_shop_owner_profile.html",
                    {"shop_owner": shop_owner},
                )

            if not password_is_valid(request, new_password, shop_owner):
                return render(
                    request,
                    "accounts/edit_shop_owner_profile.html",
                    {"shop_owner": shop_owner},
                )

            shop_owner.set_password(new_password)
            messages.success(
                request, _("رمز عبور با موفقیت به‌روزرسانی شد! لطفاً دوباره وارد شوید.")
            )
            shop_owner.save()
            logout(request)
            # Clear session
            if "shop_owner_id" in request.session:
                del request.session["shop_owner_id"]
                del request.session["shop_owner_name"]
                del request.session["shop_owner_store"]
            return redirect("shop_owner_login")

        shop_owner.save()
        # Update session store name
        request.session["shop_owner_store"] = shop_owner.store_name
        messages.success(request, _("پروفایل با موفقیت به‌روزرسانی شد!"))
        return redirect("shop_owner_dashboard")
    return render(
        request, "accounts/edit_shop_owner_profile.html", {"shop_owner": shop_owner}
    )


def forgot_password(request):
    """Forgot password selection page."""
    return render(request, "accounts/forgot_password.html")


def verify_customer_security(request: HttpRequest) -> HttpResponse:
    """Run the bounded two-question recovery flow for a customer."""
    return verify_security(request, "customer")


def verify_shop_owner_security(request: HttpRequest) -> HttpResponse:
    """Run the bounded two-question recovery flow for a seller."""
    return verify_security(request, "shop_owner")
