from typing import Optional

from django.contrib.auth.hashers import check_password, make_password
from django.contrib.auth.models import AbstractUser
from django.db import models
from django.utils.crypto import salted_hmac

from .security import normalize_answer


class SecurityAnswersMixin:
    """Store recovery answers as salted hashes for either account type."""

    def set_security_answers(self, first: str, second: str) -> None:
        """Hash normalized answers; empty legacy answers are unusable."""
        self.security_answer1 = make_password(normalize_answer(first) or None)
        self.security_answer2 = make_password(normalize_answer(second) or None)

    def check_security_answer(self, number: int, answer: str) -> bool:
        """Verify one nonempty answer without accepting plaintext storage."""
        normalized = normalize_answer(answer)
        if number not in (1, 2) or not normalized or len(normalized) > 255:
            return False
        encoded = getattr(self, f"security_answer{number}")
        return bool(encoded) and check_password(normalized, encoded)


class Customer(SecurityAnswersMixin, AbstractUser):
    """Customer user model with basic authentication and security questions."""

    email = models.EmailField(unique=True)
    security_question1 = models.CharField(max_length=255, blank=True, null=True)
    security_answer1 = models.CharField(max_length=255, blank=True, null=True)
    security_question2 = models.CharField(max_length=255, blank=True, null=True)
    security_answer2 = models.CharField(max_length=255, blank=True, null=True)
    recovery_failed_attempts = models.PositiveIntegerField(default=0)
    recovery_locked_until = models.DateTimeField(null=True, blank=True)
    failed_attempts = models.IntegerField(default=0)
    locked_until = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "customers"

    def __str__(self):
        return self.username


class ShopOwner(SecurityAnswersMixin, models.Model):
    """Shop owner model with security questions as per original CLI app."""

    name = models.CharField(max_length=100)
    store_name = models.CharField(max_length=200)
    password = models.CharField(max_length=128)
    security_question1 = models.CharField(max_length=255)
    security_answer1 = models.CharField(max_length=255)
    security_question2 = models.CharField(max_length=255)
    security_answer2 = models.CharField(max_length=255)
    role = models.IntegerField(default=1)
    address = models.TextField(blank=True, null=True, help_text="Shop address")
    phone = models.CharField(
        max_length=20,
        blank=True,
        null=True,
        help_text="Phone number with country code (e.g., +989123456789)",
    )
    recovery_failed_attempts = models.PositiveIntegerField(default=0)
    recovery_locked_until = models.DateTimeField(null=True, blank=True)
    failed_attempts = models.IntegerField(default=0)
    locked_until = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "shop_owners"

    def __str__(self):
        return f"{self.name} - {self.store_name}"

    def set_password(self, raw_password: Optional[str]) -> None:
        """Hash a seller password without saving the model."""
        self.password = make_password(raw_password)

    def check_password(self, raw_password: Optional[str]) -> bool:
        """Check a supplied password against the seller's stored hash."""
        return check_password(raw_password, self.password)

    def get_session_auth_hash(self) -> str:
        """Invalidate seller sessions and recovery grants after password changes."""
        return salted_hmac(
            "accounts.ShopOwner.session", self.password, algorithm="sha256"
        ).hexdigest()
