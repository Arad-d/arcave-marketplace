# Arcave setup

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

## Fictional demo

Follow [the isolated demo instructions](USER_EXPERIENCE.md#fictional-demo) to create a separate database with six sample products, fictional customer and seller accounts, and a sample purchase. The demo settings separate its database, media and browser cookies from your normal installation. The seed command refuses to overwrite existing business data.

## Languages

Use the English / فارسی button in the header (next to the customer cart) to switch languages while staying on the current page. Your choice is stored for one year; without a saved choice, the browser language is used when supported, with Persian as the fallback. Labels, forms, messages, categories, order status and error pages are translated. User-entered product descriptions, reviews, store names and security questions remain in their original language. Prices stay in Iranian rials; English displays the `IRR` label.

The English source and compiled catalogs live in `django_project/locale/en/LC_MESSAGES/`. Both are committed, so a normal checkout runs without installing gettext. When editing translations, install GNU gettext (`brew install gettext` on macOS or `sudo apt-get install gettext` on Ubuntu), then run from the repository root:

```bash
python django_project/manage.py makemessages -l en --no-wrap --ignore=.venv --ignore=venv --ignore=.backups
# Edit django_project/locale/en/LC_MESSAGES/django.po.
python django_project/manage.py compilemessages -l en
```

GitHub checks that the compiled catalog matches its source. Language tests exercise public, customer and seller pages, validation messages, recovery forms and language switching with CSRF protection.

## Appearance

Use the ☀️ / 🌙 switch at the outer corner of the header to change between light and night mode. The first visit follows your system appearance; an explicit choice is saved in this browser. The control is keyboard accessible and stays in the header corner on mobile, in both Persian and English.

## Sign-in and returning visits

The Arcave logo opens the welcome page for guests, the catalog for signed-in customers, and the dashboard for signed-in sellers. Guest welcome and account pages omit the redundant customer sign-in link in the header; the catalog still offers sign-in when needed.

New successful customer and seller sign-ins last 30 days in the same browser. Reopening the home page resumes the existing account rather than showing registration choices. Sign-out revokes that session, and password changes retain their existing session-revocation behavior. Clearing cookies, private browsing, or expiration requires sign-in again; existing sessions retain their previous expiry until the next sign-in.

Registration carries a valid same-site destination into sign-in. Login returns to that page; interrupted cart actions return to a review page and are never automatically replayed. Invalid login forms preserve the account name and show associated field errors while leaving passwords blank. Empty or malformed forms do not consume password attempts.
