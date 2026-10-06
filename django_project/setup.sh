#!/usr/bin/env bash
# Prepare the development environment without changing an existing database.
set -euo pipefail

project_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$project_dir"
python3 -c 'import sys; sys.exit(0 if sys.version_info >= (3, 10) else "Python 3.10 or newer is required.")'
if [[ ! -d .venv ]]; then
    python3 -m venv .venv
fi
.venv/bin/python -m pip install -r requirements-dev.txt
.venv/bin/python - <<'PY'
from pathlib import Path
from django.core.management.utils import get_random_secret_key

env_file = Path('.env')
try:
    with env_file.open('x') as output:
        env_file.chmod(0o600)
        output.write(Path('.env.example').read_text().replace('DJANGO_SECRET_KEY=\n', f'DJANGO_SECRET_KEY={get_random_secret_key()}\n'))
    print('Created private .env with a new development secret.')
except FileExistsError:
    print('Preserved existing .env configuration.')
PY
cat <<'TEXT'
Environment ready. Next:
  1. Configure DB_NAME, DB_USER, DB_PASSWORD, DB_HOST and DB_PORT in .env.
  2. Create that database using your PostgreSQL administrator account.
  3. For an existing database, create and verify a backup before migrations.
  4. Run:
       source .venv/bin/activate
       python manage.py migrate
       python manage.py runserver

Tests (database role needs CREATEDB permission):
  python manage.py test accounts shop arcave --settings=arcave.test_settings
TEXT
