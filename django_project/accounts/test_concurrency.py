"""PostgreSQL integration tests for concurrent recovery requests."""

from concurrent.futures import ThreadPoolExecutor
from threading import Barrier

from django.conf import settings
from django.contrib.auth.hashers import make_password
from django.core import signing
from django.db import close_old_connections
from django.test import Client, TransactionTestCase, skipUnlessDBFeature
from django.urls import reverse

from .models import Customer
from .recovery import RECOVERY_SALT


class ConcurrentRecoveryTests(TransactionTestCase):
    """Exercise database locks using independent connections and browser sessions."""

    def setUp(self) -> None:
        """Create one account protected by the production hashing mechanism."""
        self.account = Customer.objects.create_user(
            username="concurrent-customer",
            email="concurrent@example.com",
            password="Original-password-1",
            security_question1="First?",
            security_question2="Second?",
            security_answer1=make_password("first"),
            security_answer2=make_password("second"),
        )

    @skipUnlessDBFeature("has_select_for_update")
    def test_parallel_guesses_cannot_bypass_attempt_limit(self) -> None:
        """Concurrent guesses serialize at the account row and stop at the lock threshold."""
        count = settings.RECOVERY_MAX_ATTEMPTS + 1
        clients = [Client() for _ in range(count)]
        url = reverse("verify_customer_security")
        for client in clients:
            client.post(url, {"username": self.account.username})
        barrier = Barrier(count)

        def guess(client: Client) -> int:
            """Send one answer from an independent database connection."""
            close_old_connections()
            try:
                barrier.wait(timeout=10)
                return client.post(url, {"answer1": "wrong"}).status_code
            finally:
                close_old_connections()

        with ThreadPoolExecutor(max_workers=count) as executor:
            statuses = list(executor.map(guess, clients))
        self.assertEqual(statuses, [200] * count)
        self.account.refresh_from_db()
        self.assertEqual(
            self.account.recovery_failed_attempts, settings.RECOVERY_MAX_ATTEMPTS
        )
        self.assertIsNotNone(self.account.recovery_locked_until)
        self.assertTrue(
            all("recovery_grant" not in client.session for client in clients)
        )

    @skipUnlessDBFeature("has_select_for_update")
    def test_concurrent_grant_redemption_succeeds_once(self) -> None:
        """Two simultaneous uses of a valid grant cannot both change the password."""
        grant = signing.dumps(
            {
                "type": "customer",
                "id": self.account.pk,
                "auth_hash": self.account.get_session_auth_hash(),
            },
            salt=RECOVERY_SALT,
        )
        clients = [Client(), Client()]
        for client in clients:
            session = client.session
            session["recovery_grant"] = grant
            session.save()
        barrier = Barrier(2)
        url = reverse("reset_password", args=["customer", self.account.pk])

        def reset(item: tuple[int, Client]) -> str:
            """Try one reset on an independent database connection."""
            index, client = item
            close_old_connections()
            try:
                barrier.wait(timeout=10)
                password = f"Different-reset-Alpha-{index}"
                response = client.post(
                    url, {"new_password": password, "confirm_password": password}
                )
                return response.url
            finally:
                close_old_connections()

        with ThreadPoolExecutor(max_workers=2) as executor:
            redirects = list(executor.map(reset, enumerate(clients)))
        self.assertCountEqual(
            redirects, [reverse("customer_login"), reverse("forgot_password")]
        )
        self.account.refresh_from_db()
        self.assertTrue(
            any(
                self.account.check_password(f"Different-reset-Alpha-{index}")
                for index in range(2)
            )
        )
