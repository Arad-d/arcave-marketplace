# Arcave Marketplace

A Persian and English marketplace prototype built with Python and Django. Sellers manage their stores and product inventory, while customers browse products, use a shopping cart, and record purchases.

## Features

- Separate customer and shop-owner registration, login, and dashboards.
- Product images, categories, search, and pagination.
- Shopping carts, concurrent inventory protection, and durable order receipts.
- Product comments and seller replies.
- Store profiles and seller sales summaries.
- Persian/English language switch, automatic RTL/LTR layouts, Iranian rial prices, and Tehran time zone.

## Project structure

- `django_project/`: Django website, with `accounts` and `shop` applications.
- `main.py`: original SQLite-based terminal prototype, retained to show the project's evolution.
- `AGENTS.md`: development guidance for the Django application.
- `MAINTENANCE.md`: test commands, CI, error pages and logging.

The website uses Django templates, CSS, PostgreSQL, and Pillow for product images. Local databases, uploaded files, credentials, and generated files are excluded from version control.

## Run the website locally

Use Python 3.10–3.14, Django 5.2 and PostgreSQL 17 (the version used in CI). The dependency file keeps Django within its 5.2 series.

```bash
cd django_project
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements-dev.txt
# For a new checkout only; preserve any existing .env.
cp .env.example .env
python -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"
```

Paste the generated key into `DJANGO_SECRET_KEY` in `.env`, configure your PostgreSQL credentials, and create a database matching `DB_NAME`. The example uses `arcave_db`. Keep `.env` private. With your PostgreSQL administrator account, you can create the development database using `createdb -h localhost -U postgres arcave_db`; adjust the host and role to match your installation. Keep `DJANGO_DEBUG=True` for local development. Back up and verify an existing database before applying migrations.

```bash
python manage.py migrate
python manage.py runserver
```

Open http://127.0.0.1:8000 and register a customer or shop owner. Uploaded product images are stored locally in `django_project/media/`.

On Windows, activate the environment with `.venv\Scripts\activate`.

On macOS/Linux, `bash django_project/setup.sh` from the repository root can prepare `.venv`, install the development dependencies, and create a private `.env` with a generated secret if one does not exist. It preserves existing configuration and prints the database/migration steps for you to complete. Persian setup instructions are in [django_project/README.md](django_project/README.md).

For a deployed environment, install `requirements.txt`, follow [SECURITY.md](SECURITY.md), collect static assets with `python manage.py collectstatic --noinput`, and serve the resulting `django_project/staticfiles/` through your hosting setup.

## Current status and planned improvements

This repository preserves the initial development version and subsequent improvements. It is a learning and portfolio prototype and is not ready to handle real customer accounts or payments.

The security updates hash seller passwords and recovery answers, require both answers, expire recovery sessions, limit guesses across browser sessions, enforce password validation, protect state-changing requests with POST and CSRF, and validate image uploads. Seller sessions are revoked after password changes. Apply the migrations with `python manage.py migrate` before using an existing database. See [SECURITY.md](SECURITY.md) for limits and deployment configuration.

Shopping reliability now includes atomic checkout, duplicate-submission protection, validated cart quantities, preserved purchase details, and unique order numbers with fulfillment status. See [SHOPPING.md](SHOPPING.md) for the completed checklist, migration behavior, and remaining limits.

Account security, credential migration, and shopping reliability are covered by regression tests:

```bash
cd django_project
python manage.py test accounts shop arcave --settings=arcave.test_settings
```

GitHub runs the complete PostgreSQL suite on every push and pull request using Python 3.10 and 3.14. [MAINTENANCE.md](MAINTENANCE.md) contains the completed maintenance checklist, database permissions for tests, coverage commands, and how to investigate errors using request references.

Remaining work:

- Checkout records purchases and updates inventory; no payment gateway is integrated.
- Configure and verify the actual production domain, TLS certificate, reverse proxy, and media hosting before deployment.
- Extend validation and error handling beyond the account and product forms.
- Add cancellation, refunds, delivery tracking, and payment reconciliation when integrating real payments.
- The terminal prototype's purchase flow references a table it does not initialize.

These improvements will be tracked through subsequent commits. Embedded configuration credentials have been moved into a local, ignored `.env` file before the initial publication.

## Languages

Use the English / فارسی button in the header (next to the customer cart) to switch languages while staying on the current page. Your choice is stored for one year; without a saved choice, the browser language is used when supported, with Persian as the fallback. Labels, forms, messages, categories, order status and error pages are translated. User-entered product descriptions, reviews, store names and security questions remain in their original language. Prices stay in Iranian rials; English displays the `IRR` label.

The English source and compiled catalogs live in `django_project/locale/en/LC_MESSAGES/`. Both are committed, so a normal checkout runs without installing gettext. When editing translations, install GNU gettext (`brew install gettext` on macOS or `sudo apt-get install gettext` on Ubuntu), then run from the repository root:

```bash
python django_project/manage.py makemessages -l en --no-wrap --ignore=.venv --ignore=venv --ignore=.backups
# Edit django_project/locale/en/LC_MESSAGES/django.po.
python django_project/manage.py compilemessages -l en
```

GitHub checks that the compiled catalog matches its source. Language tests exercise public, customer and seller pages, validation messages, recovery forms and language switching with CSRF protection.
