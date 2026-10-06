from datetime import timedelta

from django.contrib import messages
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.http import HttpRequest, HttpResponse
from django.middleware.csrf import rotate_token
from django.shortcuts import redirect, render
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from django.views.decorators.http import require_POST

from .forms import CustomerSignupForm, ShopOwnerSignupForm
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


def landing(request):
    """Landing page with login/signup options."""
    return render(request, "accounts/landing.html")


def customer_signup(request: HttpRequest) -> HttpResponse:
    """Register an account after validating and hashing all credentials."""
    form = CustomerSignupForm(request.POST if request.method == "POST" else None)
    if request.method == "POST":
        if form.is_valid():
            form.save()
            messages.success(request, _("حساب با موفقیت ایجاد شد. لطفاً وارد شوید."))
            return redirect("customer_login")
    return render(request, "accounts/customer_signup.html", {"form": form})


def customer_login(request):
    """Customer login view."""
    if request.method == "POST":
        username = request.POST.get("username")
        password = request.POST.get("password")

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
                return render(request, "accounts/customer_login.html")
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
            return redirect("customer_dashboard")
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

    return render(request, "accounts/customer_login.html")


def shop_owner_signup(request: HttpRequest) -> HttpResponse:
    """Register an account after validating and hashing all credentials."""
    form = ShopOwnerSignupForm(request.POST if request.method == "POST" else None)
    if request.method == "POST":
        if form.is_valid():
            form.save()
            messages.success(request, _("حساب با موفقیت ایجاد شد. لطفاً وارد شوید."))
            return redirect("shop_owner_login")
    return render(request, "accounts/shop_owner_signup.html", {"form": form})


def shop_owner_login(request):
    """Shop owner login view."""
    if request.method == "POST":
        name = request.POST.get("name")
        password = request.POST.get("password")

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
                return render(request, "accounts/shop_owner_login.html")
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
            return redirect("shop_owner_dashboard")
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

    return render(request, "accounts/shop_owner_login.html")


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
