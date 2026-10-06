"""Opt-in fictional showcase, isolated from the configured application database."""

import os
from pathlib import Path

from django.core.exceptions import ImproperlyConfigured

from .settings import *  # noqa: F403

DEMO_MODE = True
DEMO_DATABASE_NAME = os.environ.get("DEMO_DB_NAME", "")
if not DEMO_DATABASE_NAME.startswith("demo_"):
    raise ImproperlyConfigured("DEMO_DB_NAME must name a separate demo_ database.")
if DEMO_DATABASE_NAME == DATABASES["default"]["NAME"]:  # noqa: F405
    raise ImproperlyConfigured("The demo database must differ from DB_NAME.")
DATABASES["default"]["NAME"] = DEMO_DATABASE_NAME  # noqa: F405
MEDIA_ROOT = Path(
    os.environ.get("DEMO_MEDIA_ROOT", BASE_DIR / ".demo-media")  # noqa: F405
)  # noqa: F405
SESSION_COOKIE_NAME = "arcave_demo_session"
CSRF_COOKIE_NAME = "arcave_demo_csrf"
LANGUAGE_COOKIE_NAME = "arcave_demo_language"
