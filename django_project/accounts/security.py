"""Shared password, answer, and session security helpers."""

import unicodedata
from typing import Optional

from django.contrib import messages
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.http import HttpRequest


def normalize_answer(answer: Optional[str]) -> str:
    """Normalize answers consistently before hashing or checking them."""
    return unicodedata.normalize("NFKC", answer or "").strip().casefold()


def validate_new_password(password: str, user: object) -> None:
    """Enforce a bounded password and Django's configured strength validators."""
    if not password or len(password) > 128:
        raise ValidationError("رمز عبور باید بین ۸ و ۱۲۸ نویسه باشد.")
    validate_password(password, user=user)


def password_is_valid(request: HttpRequest, password: str, user: object) -> bool:
    """Show safe, user-facing validation errors for password changes."""
    try:
        validate_new_password(password, user)
    except ValidationError as error:
        for message in error.messages:
            messages.error(request, message)
        return False
    return True
