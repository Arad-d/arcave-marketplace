"""Expiring, account-bound recovery with durable per-account attempt limits."""

from datetime import timedelta
from typing import Optional

from django.conf import settings
from django.contrib import messages
from django.core import signing
from django.db import transaction
from django.http import HttpRequest, HttpResponse
from django.shortcuts import redirect, render
from django.utils import timezone
from django.utils.crypto import constant_time_compare
from django.utils.translation import gettext_lazy as _
from django.views.decorators.http import require_http_methods

from .models import Customer, ShopOwner
from .security import password_is_valid

RECOVERY_SALT = "accounts.password-recovery"


def clear_recovery(request: HttpRequest) -> None:
    """Remove challenges, grants, and state left by the legacy recovery flow."""
    for key in (
        "recovery_challenge",
        "recovery_grant",
        "verified_for_reset",
        "verified_reset_user_id",
        "reset_user_type",
        "reset_customer_id",
        "reset_shop_owner_id",
        "security_step",
        "shop_security_step",
    ):
        request.session.pop(key, None)


def recovery_remaining(account: Customer | ShopOwner) -> int:
    """Report the longer of login and recovery lockouts without modifying it."""
    deadlines = [
        value
        for value in (account.locked_until, account.recovery_locked_until)
        if value
    ]
    if not deadlines:
        return 0
    return max(0, int((max(deadlines) - timezone.now()).total_seconds()) + 1)


def record_recovery_failure(account: Customer | ShopOwner) -> None:
    """Count each failed answer under the caller's database row lock."""
    if (
        account.recovery_locked_until
        and account.recovery_locked_until <= timezone.now()
    ):
        account.recovery_failed_attempts = 0
        account.recovery_locked_until = None
    account.recovery_failed_attempts += 1
    if account.recovery_failed_attempts >= settings.RECOVERY_MAX_ATTEMPTS:
        account.recovery_locked_until = timezone.now() + timedelta(
            seconds=settings.RECOVERY_LOCK_SECONDS
        )
    account.save(update_fields=["recovery_failed_attempts", "recovery_locked_until"])


def challenge_payload(request: HttpRequest, user_type: str) -> Optional[dict]:
    """Accept only a fresh challenge for this account type."""
    challenge = request.session.get("recovery_challenge")
    if not isinstance(challenge, dict) or challenge.get("type") != user_type:
        return None
    age = timezone.now().timestamp() - challenge.get("started_at", 0)
    if not 0 <= age < settings.RECOVERY_TIMEOUT_SECONDS:
        clear_recovery(request)
        return None
    return challenge


@require_http_methods(["GET", "POST"])
def verify_security(request: HttpRequest, user_type: str) -> HttpResponse:
    """Require both answers in order and limit guesses across browser sessions."""
    model = Customer if user_type == "customer" else ShopOwner
    identity_field = "username" if user_type == "customer" else "name"
    template = f"accounts/verify_{user_type}_security.html"
    if request.method == "POST" and identity_field in request.POST:
        clear_recovery(request)
        account = model.objects.filter(
            **{identity_field: request.POST[identity_field]}
        ).first()
        if account is None or (user_type == "customer" and not account.is_active):
            messages.error(request, _("امکان بازیابی با این اطلاعات وجود ندارد."))
            return render(request, template, {"step": 1})
        remaining = recovery_remaining(account)
        if remaining:
            return render(
                request, template, {"step": 1, "locked": True, "remaining": remaining}
            )
        request.session["recovery_challenge"] = {
            "type": user_type,
            "id": account.pk,
            "started_at": timezone.now().timestamp(),
            "stage": 2,
            "auth_hash": account.get_session_auth_hash(),
        }
        return render(
            request, template, {"step": 2, "question": account.security_question1}
        )

    challenge = challenge_payload(request, user_type)
    if challenge is None:
        if request.method == "POST":
            messages.error(request, _("لطفاً بازیابی رمز عبور را دوباره شروع کنید."))
        return render(request, template, {"step": 1})

    with transaction.atomic():
        account = model.objects.select_for_update().filter(pk=challenge["id"]).first()
        if (
            account is None
            or (user_type == "customer" and not account.is_active)
            or not constant_time_compare(
                challenge["auth_hash"], account.get_session_auth_hash()
            )
        ):
            clear_recovery(request)
            return redirect("forgot_password")
        remaining = recovery_remaining(account)
        if remaining:
            clear_recovery(request)
            return render(
                request, template, {"step": 1, "locked": True, "remaining": remaining}
            )
        stage = challenge["stage"]
        if request.method == "GET":
            return render(
                request,
                template,
                {
                    "step": stage,
                    "question": getattr(account, f"security_question{stage - 1}"),
                },
            )
        answer_key = "answer1" if stage == 2 else "answer2"
        if not account.check_security_answer(
            stage - 1, request.POST.get(answer_key, "")
        ):
            record_recovery_failure(account)
            clear_recovery(request)
            messages.error(request, _("پاسخ نادرست است. بازیابی را دوباره شروع کنید."))
            remaining = recovery_remaining(account)
            return render(
                request,
                template,
                {"step": 1, "locked": bool(remaining), "remaining": remaining},
            )
        if stage == 2:
            challenge["stage"] = 3
            request.session["recovery_challenge"] = challenge
            return render(
                request, template, {"step": 3, "question": account.security_question2}
            )
        clear_recovery(request)
        request.session["recovery_grant"] = signing.dumps(
            {
                "type": user_type,
                "id": account.pk,
                "auth_hash": account.get_session_auth_hash(),
            },
            salt=RECOVERY_SALT,
        )
        return redirect("reset_password", user_type=user_type, user_id=account.pk)


@require_http_methods(["GET", "POST"])
def reset_password(request: HttpRequest, user_type: str, user_id: int) -> HttpResponse:
    """Consume an expiring reset grant while locking the verified account."""
    try:
        grant = signing.loads(
            request.session.get("recovery_grant", ""),
            salt=RECOVERY_SALT,
            max_age=settings.RECOVERY_TIMEOUT_SECONDS,
        )
    except signing.BadSignature:
        grant = None
    if (
        not isinstance(grant, dict)
        or user_type not in ("customer", "shop_owner")
        or grant.get("type") != user_type
        or grant.get("id") != user_id
    ):
        clear_recovery(request)
        messages.error(request, _("درخواست بازیابی نامعتبر یا منقضی شده است."))
        return redirect("forgot_password")
    model = Customer if user_type == "customer" else ShopOwner
    with transaction.atomic():
        account = model.objects.select_for_update().filter(pk=user_id).first()
        if (
            account is None
            or (user_type == "customer" and not account.is_active)
            or recovery_remaining(account)
            or not constant_time_compare(
                grant.get("auth_hash", ""), account.get_session_auth_hash()
            )
        ):
            clear_recovery(request)
            return redirect("forgot_password")
        if request.method == "POST":
            password = request.POST.get("new_password", "")
            if password != request.POST.get("confirm_password", ""):
                messages.error(request, _("رمزهای عبور مطابقت ندارند."))
            elif password_is_valid(request, password, account):
                account.set_password(password)
                account.failed_attempts = 0
                account.locked_until = None
                account.recovery_failed_attempts = 0
                account.recovery_locked_until = None
                account.save(
                    update_fields=[
                        "password",
                        "failed_attempts",
                        "locked_until",
                        "recovery_failed_attempts",
                        "recovery_locked_until",
                    ]
                )
                clear_recovery(request)
                messages.success(
                    request, _("رمز عبور تغییر کرد. لطفاً دوباره وارد شوید.")
                )
                return redirect(f"{user_type}_login")
    return render(request, "accounts/reset_password.html", {"user_type": user_type})
