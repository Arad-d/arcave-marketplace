"""PostgreSQL test configuration; only use with Django's test command."""

import os
from copy import deepcopy

from django.core.exceptions import ImproperlyConfigured

from . import settings as application_settings

# Reuse every production validation and middleware setting without wildcard imports.
globals().update(
    {
        name: getattr(application_settings, name)
        for name in dir(application_settings)
        if name.isupper()
    }
)
DATABASES = deepcopy(application_settings.DATABASES)
test_database_name = os.environ.get("TEST_DB_NAME", "test_arcave")
if (
    not test_database_name.startswith("test_")
    or test_database_name == DATABASES["default"]["NAME"]
):
    raise ImproperlyConfigured(
        "TEST_DB_NAME must start with test_ and differ from DB_NAME."
    )
DATABASES["default"]["TEST"] = {"NAME": test_database_name}
ALLOWED_HOSTS = ["testserver", "localhost", "127.0.0.1"]
SECURE_SSL_REDIRECT = False
SESSION_COOKIE_SECURE = False
CSRF_COOKIE_SECURE = False
EMAIL_BACKEND = "django.core.mail.backends.locmem.EmailBackend"
