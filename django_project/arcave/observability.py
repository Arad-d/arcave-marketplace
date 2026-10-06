"""Correlate errors without logging credentials, request bodies or exception text."""

import json
import logging
from collections.abc import Callable
from contextvars import ContextVar
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from django.http import HttpRequest, HttpResponse

current_request = ContextVar("arcave_request", default=None)


class RequestReferenceMiddleware:
    """Give each request a server-generated reference shared by responses and logs."""

    def __init__(self, get_response: Callable) -> None:
        """Store the next synchronous middleware handler."""
        self.get_response = get_response

    def __call__(self, request: HttpRequest) -> HttpResponse:
        """Keep request context isolated across threads and reset it after each response."""
        request.error_reference = uuid4().hex
        token = current_request.set(request)
        try:
            response = self.get_response(request)
            response["X-Request-ID"] = request.error_reference
            return response
        finally:
            current_request.reset(token)


class SafeJsonFormatter(logging.Formatter):
    """Emit diagnostic metadata, excluding untrusted messages and exception values."""

    def format(self, record: logging.LogRecord) -> str:
        """Record location and error type without SQL, local variables or form data."""
        request = getattr(record, "request", None)
        if not isinstance(request, HttpRequest):
            request = current_request.get()
        payload = {
            "time": datetime.fromtimestamp(record.created, timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "location": f"{Path(record.pathname).name}:{record.lineno}",
            "event": (
                "application_error"
                if record.levelno >= logging.ERROR
                else "application_event"
            ),
        }
        if request is not None:
            match = getattr(request, "resolver_match", None)
            payload.update(
                request_id=getattr(request, "error_reference", None),
                method=request.method,
                route=match.route if match else None,
            )
        if hasattr(record, "status_code"):
            payload["status"] = record.status_code
        if record.exc_info and record.exc_info[0]:
            payload["exception"] = record.exc_info[0].__name__
            frames = []
            trace = record.exc_info[2]
            while trace is not None:
                code = trace.tb_frame.f_code
                frames.append(
                    f"{Path(code.co_filename).name}:{trace.tb_lineno}:{code.co_name}"
                )
                trace = trace.tb_next
            payload["stack"] = frames[-30:]
        return json.dumps(payload, ensure_ascii=True)
