# Arcave Marketplace

A Persian-language marketplace prototype built with Python and Django. Sellers manage their stores and product inventory, while customers browse products, use a shopping cart, and record purchases.

## Features

- Separate customer and shop-owner registration, login, and dashboards.
- Product images, categories, search, and pagination.
- Shopping carts, stock tracking, and purchase history.
- Product comments and seller replies.
- Store profiles and seller sales summaries.
- Persian interface, Iranian rial prices, and Tehran time zone.

## Project structure

- `django_project/`: Django website, with `accounts` and `shop` applications.
- `main.py`: original SQLite-based terminal prototype, retained to show the project's evolution.
- `AGENTS.md`: development guidance originally written for the terminal prototype.

The website uses Django templates, CSS, PostgreSQL, and Pillow for product images. Local databases, uploaded files, credentials, and generated files are excluded from version control.

## Run the website locally

Use Python 3.10 or newer and a local PostgreSQL installation. Choose a Django release compatible with your Python version.

```bash
cd django_project
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
python -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"
```

Paste the generated key into `DJANGO_SECRET_KEY` in `.env`, configure your PostgreSQL credentials, and create a database matching `DB_NAME`. The example uses `arcave_db`. Keep `.env` private.

```bash
python manage.py migrate
python manage.py runserver
```

Open http://127.0.0.1:8000 and register a customer or shop owner. Uploaded product images are stored locally in `django_project/media/`.

On Windows, activate the environment with `.venv\Scripts\activate`.

The existing `setup.sh` and nested README are legacy setup instructions; follow the environment-based instructions above for this published version.

## Current status and planned improvements

This repository preserves the initial development version. It is a learning and portfolio prototype and is not ready to handle real customer accounts or payments.

- Checkout records purchases and updates inventory; no payment gateway is integrated.
- Seller passwords and security answers still require secure hashing.
- Password recovery needs account-specific authorization checks.
- Checkout needs protection against simultaneous purchases and stricter HTTP method checks.
- Input validation and purchase eligibility for comments need strengthening.
- The test files are placeholders; automated coverage will be added as the application improves.
- The terminal prototype's purchase flow references a table it does not initialize.

These improvements will be tracked through subsequent commits. Embedded configuration credentials have been moved into a local, ignored `.env` file before the initial publication.
