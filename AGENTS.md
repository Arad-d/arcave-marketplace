# Working on Arcave

The active application is the Django website in `django_project/`. `main.py` is the historical SQLite CLI prototype; change it only for an explicit CLI request.

## Development workflow

1. Read [README.md](README.md) for setup and [MAINTENANCE.md](MAINTENANCE.md) for tests, CI and troubleshooting.
2. Make website changes in the relevant Django application. Use type hints and docstrings for new functions, explicit imports, and focused functions.
3. Run Django checks and the relevant tests. For account, shopping, schema or middleware changes, run the full PostgreSQL suite documented in MAINTENANCE.md. Use Django's test runner; the suite includes transaction and migration tests.
4. Include model migrations when needed and check for missing migrations. Use a compatible PostgreSQL backup tool and verify its archive before applying migrations to an existing user database.
5. Review the diff and exclude private `.env` files, databases, backups and uploaded media from commits.

## Domain constraints

- Before changing authentication, recovery, permissions or uploads, read [SECURITY.md](SECURITY.md).
- Before changing checkout, cart mutation, inventory, purchase history or order status, read [SHOPPING.md](SHOPPING.md). Preserve transaction boundaries, consistent lock order and receipt snapshots. Verify concurrency against PostgreSQL.
- Keep stored passwords and recovery answers hashed. Use parameterized database access and validate user input.
- Render user-facing errors without exception details. Use the configured logger for failures; see MAINTENANCE.md for retained metadata and privacy limits.
- Keep the Persian interface and right-to-left direction in customer-facing pages.

## Scope of checks

Use installed project dependencies from `requirements-dev.txt`. Format changed Python files with Black and check them with Ruff's `E4,E7,E9,F,I` rules. Avoid reformatting unrelated legacy files. The GitHub Tests workflow runs application checks, migration validation, dependency checks and the complete PostgreSQL test suite for every push and pull request.
