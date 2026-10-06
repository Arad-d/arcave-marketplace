# Tests and maintenance

## Completed checklist

- [x] Test carts, checkout, inventory, reviews, and seller permissions.
- [x] Add PostgreSQL tests for simultaneous purchases.
- [x] Run automated tests on GitHub for every change.
- [x] Update outdated setup instructions and project documentation.
- [x] Add useful error logging and friendly error pages.

## Local checks

Use the virtual environment described in [README.md](README.md) and a running PostgreSQL server. Install development tools with `python -m pip install -r requirements-dev.txt` from `django_project/`.

The test database role must have `CREATEDB` permission. Django creates and drops the database named by `TEST_DB_NAME` (default `test_arcave`). Its name must begin with `test_` and differ from `DB_NAME`. Reserve it for tests; it must never contain data you want to retain. Tests run migrations automatically, including migration rollback/backfill cases. Avoid `--parallel` because the suite also manages its own independent connections and migration state.

```bash
cd django_project
python manage.py check
python manage.py makemigrations --check --dry-run
python -m pip check
python manage.py test accounts shop arcave --settings=arcave.test_settings --verbosity=2
```

Use development configuration (`DJANGO_DEBUG=True`) for the test process. The test runner disables debug responses; the error-page tests also explicitly disable HTTPS redirects when exercising local HTTP. The test settings preserve PostgreSQL and real password hashing. Do not start the website with `arcave.test_settings`.

Focused examples:

```bash
python manage.py test shop.test_reliability --settings=arcave.test_settings
python manage.py test shop.test_journey --settings=arcave.test_settings
python manage.py test arcave.test_runtime --settings=arcave.test_settings
```

Coverage:

```bash
python -m coverage run --source=accounts,shop,arcave manage.py test accounts shop arcave --settings=arcave.test_settings
python -m coverage report --skip-empty
```

Coverage reports exclude tests, generated migrations and server entry points so the percentage reflects application code.

The suite covers account hashing and recovery, permissions and CSRF, uploaded images, cart operations, order receipts and stock, stale seller/admin edits, legacy data migrations, and error responses. PostgreSQL transaction tests use separate connections for competing buyers, duplicate checkout, separate tabs, seller replies, and recovery requests. They skip on databases without row locking; CI always uses PostgreSQL so these checks execute.

Format changed Python files with `python -m black <files>` and check imports/basic correctness with `python -m ruff check --isolated --select E4,E7,E9,F,I <files>`. Check shell changes with `bash -n django_project/setup.sh` from the repository root.

## GitHub automation

[Tests workflow](.github/workflows/tests.yml) runs on every push and pull request, and can also be started manually from the repository's Actions tab. Both Python 3.10 and 3.14 jobs start an isolated PostgreSQL 17 service, install supported dependency versions, validate Django configuration, detect missing migrations, apply migrations to an empty database, check dependency compatibility, and run the complete suite with a coverage summary.

The credentials in this workflow are disposable values for its isolated database. It requires no application credentials or repository secrets and has read-only repository permissions. Action versions are pinned to commit IDs. Dependencies stay within supported major/minor families and receive compatible updates when CI installs them; this is not a fully locked dependency set. Evaluate dependency updates through the full suite. CI failures appear in the commit/PR checks; open the failed step to diagnose them. Branch protection is a separate repository setting and is not enabled by adding this workflow.

## Error pages

With `DJANGO_DEBUG=False`, HTTP 400, 403, 404 and 500 responses use a Persian page with an explanation, home link and reference number. CSRF rejections explain that the form should be reopened and submitted again. The pages have inline styling and render without session, authentication, database queries, remote fonts or static-file services, so a database outage does not break the fallback page. Error responses use `Cache-Control: no-store`.

Django still displays its diagnostic pages for 400/404/500 in development debug mode. Test production error handling with `arcave.test_runtime`, or use a separate local preview configuration with debug disabled and local HTTPS settings; keep the actual production HTTPS protections enabled. No intentional crash endpoint is installed in the website.

## Logs and troubleshooting

Every request receives a generated `X-Request-ID`; client-supplied references are ignored. That reference appears on error pages and in structured JSON error records on stderr. Capture stderr using the deployment platform's logging facility; no unbounded log file is written into the repository.

Records retain UTC time, severity, logger, source location, request reference, method, matched route pattern, HTTP status when supplied by Django, exception class and up to 30 traceback locations. A handled checkout database failure also produces an error record and a friendly cart message. Unhandled failures use Django's error logging and roll into the appropriate error response.

The formatter deliberately excludes free-form log messages, exception text, source lines, local variables, SQL, raw URL/query strings, request bodies, cookies and authorization headers. This prevents those channels from leaking submitted passwords, recovery answers and database details. Third-party servers or externally configured handlers may have their own access logs; configure their retention and privacy separately. Use the request reference plus exception class and code locations to reproduce a problem with fictional data locally. Do not turn on production debug mode to investigate it.

For a missing database or permission error, check the PostgreSQL service, `.env` connection fields, and the test role's `CREATEDB` permission. For pending schema changes, inspect `python manage.py showmigrations`. Before applying migrations to an existing database, use a `pg_dump` version compatible with the server and verify the private archive with `pg_restore --list`. Keep backups out of Git. Full automated backup scheduling and restore drills remain part of the production-readiness checklist.

Reference documentation: [Django error views](https://docs.djangoproject.com/en/5.2/topics/http/views/#customizing-error-views), [Django logging](https://docs.djangoproject.com/en/5.2/topics/logging/), and [GitHub PostgreSQL services](https://docs.github.com/en/actions/tutorials/use-containerized-services/create-postgresql-service-containers).
