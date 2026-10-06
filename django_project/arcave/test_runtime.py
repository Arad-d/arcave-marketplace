"""Verify real error routing and privacy of the configured diagnostic output."""

import json
import logging
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier

from django.core.exceptions import PermissionDenied, SuspiciousOperation
from django.db import OperationalError
from django.http import HttpRequest, HttpResponse
from django.test import Client, RequestFactory, SimpleTestCase, override_settings
from django.urls import path

from . import errors
from .observability import (
    RequestReferenceMiddleware,
    SafeJsonFormatter,
    current_request,
)

SECRET = "private-form-and-database-value"


def fail(request: HttpRequest, code: int) -> HttpResponse:
    """Raise representative failures through Django's real exception handlers."""
    exceptions = {
        400: SuspiciousOperation,
        403: PermissionDenied,
        500: OperationalError,
    }
    raise exceptions[code](SECRET)


def success(request: HttpRequest) -> HttpResponse:
    """Provide a normal endpoint for CSRF and reference tests."""
    return HttpResponse("ok")


urlpatterns = [path("fail/<int:code>/", fail), path("ok/", success)]
handler400 = errors.bad_request
handler403 = errors.permission_denied
handler404 = errors.page_not_found
handler500 = errors.server_error


@override_settings(
    ROOT_URLCONF=__name__,
    DEBUG=False,
    SECURE_SSL_REDIRECT=False,
    ALLOWED_HOSTS=["testserver"],
)
class ErrorPageTests(SimpleTestCase):
    """Error pages work through middleware without any database access."""

    def test_error_routes_preserve_status_and_hide_internal_details(self) -> None:
        """All four error types render Persian HTML with a matching reference."""
        client = Client(raise_request_exception=False)
        for code in (400, 403, 404, 500):
            url = "/missing/" if code == 404 else f"/fail/{code}/"
            response = client.get(url, {"secret": SECRET})
            self.assertContains(response, 'lang="fa" dir="rtl"', status_code=code)
            self.assertContains(response, 'href="/"', status_code=code)
            self.assertContains(response, response["X-Request-ID"], status_code=code)
            self.assertEqual(response["Cache-Control"], "no-store")
            self.assertNotContains(response, SECRET, status_code=code)
            self.assertNotContains(response, "Traceback", status_code=code)

    def test_csrf_rejection_explains_how_to_retry(self) -> None:
        """Missing CSRF tokens lead to a friendly refresh instruction, still HTTP 403."""
        response = Client(enforce_csrf_checks=True).post("/ok/", {"password": SECRET})
        self.assertContains(response, "فرم نیاز به تازه‌سازی دارد", status_code=403)
        self.assertNotContains(response, SECRET, status_code=403)

    def test_logs_correlate_database_errors_without_sensitive_values(self) -> None:
        """Keep the exception type and call sites while dropping bodies, SQL and secrets."""
        client = Client(raise_request_exception=False)
        with self.assertLogs("django.request", level="ERROR") as captured:
            response = client.post(
                "/fail/500/?token=" + SECRET,
                {"password": SECRET},
                HTTP_COOKIE="privatecookie=" + SECRET,
                HTTP_AUTHORIZATION="Bearer " + SECRET,
            )
        record = captured.records[0]
        output = SafeJsonFormatter().format(record)
        payload = json.loads(output)
        self.assertEqual(payload["request_id"], response["X-Request-ID"])
        self.assertEqual(payload["exception"], "OperationalError")
        self.assertEqual(payload["route"], "fail/<int:code>/")
        self.assertEqual(payload["status"], 500)
        self.assertTrue(payload["stack"])
        self.assertNotIn(SECRET, output)
        self.assertNotIn("password", output)
        self.assertNotIn("privatecookie", output)

    def test_reference_is_generated_and_not_reused_between_requests(self) -> None:
        """A client cannot inject its own log reference or inherit an earlier one."""
        first = self.client.get("/ok/", HTTP_X_REQUEST_ID=SECRET)
        second = self.client.get("/ok/")
        self.assertRegex(first["X-Request-ID"], r"^[a-f0-9]{32}$")
        self.assertNotEqual(first["X-Request-ID"], second["X-Request-ID"])
        self.assertIsNone(current_request.get())

    def test_unmatched_paths_and_log_arguments_are_not_emitted(self) -> None:
        """Arbitrary URL text and log arguments stay out of structured output."""
        with self.assertLogs("django.request", level="WARNING") as captured:
            self.client.get("/missing/" + SECRET)
        self.assertNotIn(SECRET, SafeJsonFormatter().format(captured.records[0]))
        record = logging.LogRecord(
            "shop", logging.ERROR, __file__, 1, "value=%s", (SECRET,), None
        )
        self.assertNotIn(SECRET, SafeJsonFormatter().format(record))

    def test_request_context_is_isolated_across_workers(self) -> None:
        """Concurrent requests keep their own references and release context afterwards."""
        barrier = Barrier(2)

        def view(request: HttpRequest) -> HttpResponse:
            """Wait for both requests, then echo only the current reference."""
            barrier.wait(timeout=10)
            return HttpResponse(current_request.get().error_reference)

        middleware = RequestReferenceMiddleware(view)

        def run(index: int) -> tuple:
            """Exercise the synchronous middleware on an independent thread."""
            response = middleware(RequestFactory().get("/"))
            return (
                response.content.decode(),
                response["X-Request-ID"],
                current_request.get(),
            )

        with ThreadPoolExecutor(max_workers=2) as executor:
            outcomes = list(executor.map(run, range(2)))
        self.assertNotEqual(outcomes[0][0], outcomes[1][0])
        for reference, header, remaining in outcomes:
            self.assertEqual(reference, header)
            self.assertIsNone(remaining)
