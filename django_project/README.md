# آرکیو — راه‌اندازی و نگهداری

وب‌سایت اصلی با Django 5.2 و PostgreSQL ساخته شده است. پیش‌نیازها: Python 3.10 تا 3.14 و PostgreSQL؛ آزمون‌های GitHub روی PostgreSQL 17 اجرا می‌شوند. فایل `main.py` در پوشه اصلی نسخه قدیمی خط فرمان است.

## راه‌اندازی در macOS و Linux

از پوشه اصلی مخزن اجرا کنید:

```bash
bash django_project/setup.sh
```

این اسکریپت محیط `.venv` و وابستگی‌ها را آماده می‌کند. اگر `.env` وجود نداشته باشد، آن را با یک کلید محرمانه جدید می‌سازد. تنظیمات موجود و پایگاه داده را تغییر نمی‌دهد.

در `django_project/.env` مقدارهای `DB_NAME`، `DB_USER`، `DB_PASSWORD`، `DB_HOST` و `DB_PORT` را تنظیم کنید. برای توسعه محلی `DJANGO_DEBUG=True` باشد. پایگاه داده را با حساب مدیر PostgreSQL بسازید؛ برای نمونه:

```bash
createdb -h localhost -U postgres arcave_db
cd django_project
source .venv/bin/activate
python manage.py migrate
python manage.py runserver
```

نام پایگاه داده و حساب را با تنظیمات خود هماهنگ کنید. پیش از اجرای migration روی داده‌های موجود، نسخه پشتیبان بگیرید و صحت آن را بررسی کنید. وب‌سایت در http://127.0.0.1:8000 باز می‌شود. برای ایجاد مدیر از `python manage.py createsuperuser` استفاده کنید.

## نصب دستی و Windows

```bash
cd django_project
python -m venv .venv
```

در Windows محیط را با `.venv\Scripts\activate` و در macOS/Linux با `source .venv/bin/activate` فعال کنید. سپس:

```bash
python -m pip install -r requirements-dev.txt
python -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"
```

فقط اگر `.env` ندارید، یک کپی از `.env.example` با نام `.env` بسازید. کلید تولیدشده را در `DJANGO_SECRET_KEY` قرار دهید و تنظیمات PostgreSQL را کامل کنید. پس از ایجاد پایگاه داده، دستورات `migrate` و `runserver` بالا را اجرا کنید. فایل `.env`، تصاویر کاربران و پایگاه داده را در Git قرار ندهید.

## آزمون‌ها

حساب PostgreSQL آزمون‌ها باید مجوز `CREATEDB` داشته باشد. Django یک پایگاه جدا با نام `TEST_DB_NAME` (پیش‌فرض `test_arcave`) می‌سازد و پس از آزمون حذف می‌کند. این نام باید با `test_` شروع شود و با `DB_NAME` تفاوت داشته باشد.

```bash
python manage.py check
python manage.py makemigrations --check --dry-run
python manage.py test accounts shop arcave --settings=arcave.test_settings
```

برای راه‌اندازی وب‌سایت از تنظیمات آزمون استفاده نکنید. تست خرید هم‌زمان به PostgreSQL واقعی نیاز دارد. GitHub همین آزمون‌ها را در هر push و pull request اجرا می‌کند.

## خطاها و استقرار

در حالت تولید (`DJANGO_DEBUG=False`) صفحه خطای فارسی همراه کد پیگیری نمایش داده می‌شود. گزارش‌های JSON در stderr همین کد را دارند و متن رمزها، فرم‌ها و خطاهای پایگاه داده در آن‌ها ثبت نمی‌شود. تنظیمات HTTPS و دامنه تولید را طبق راهنمای امنیت تکمیل کنید.

راهنماهای اصلی: [نصب و معرفی پروژه](../README.md)، [امنیت](../SECURITY.md)، [قابلیت اطمینان خرید](../SHOPPING.md)، [آزمون‌ها و نگهداری](../MAINTENANCE.md).
