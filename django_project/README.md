# آرکیو - پلتفرم خرید و فروش آنلاین

## راه‌اندازی سریع

**برای اجرای برنامه، لطفاً فایل `setup.sh` را اجرا کنید:**

```bash
chmod +x setup.sh
./setup.sh
```

## پیش‌نیازها

- Python 3.8 یا بالاتر
- pip

## راه‌اندازی دستی

اگر می‌خواهید به صورت دستی نصب کنید:

### ۱. ایجاد محیط مجازی
```bash
python3 -m venv venv
source venv/bin/activate  # macOS/Linux
# یا
venv\Scripts\activate  # Windows
```

### ۲. نصب وابستگی‌ها
```bash
pip install -r requirements.txt
```

### ۳. اجرای مهاجرت‌ها
```bash
python3 manage.py migrate
```

### ۵. اجرای سرور
```bash
python manage.py runserver
```

برنامه در آدرس `http://127.0.0.1:8000` در دسترس خواهد بود.

## ساختار پروژه

```
django_project/
├── accounts/                 # اپلیکیشن احراز هویت
├── shop/                     # اپلیکیشن اصلی فروشگاه
├── arcave/                   # تنظیمات پروژه
├── static/                   # فایل‌های CSS و استاتیک
├── media/                    # تصاویر آپلود شده
├── setup.sh                  # اسکریپت نصب خودکار
└── manage.py
```

## ویژگی‌ها

### امکانات مشتری:
- ثبت‌نام و ورود
- مشاهده و جستجوی محصولات
- خرید محصولات
- ثبت نظر برای محصولات خریداری شده
- مشاهده تاریخچه خرید

### امکانات فروشنده:
- ثبت‌نام فروشگاه با سوالات امنیتی
- افزودن محصول با تصویر
- مدیریت محصولات
- مشاهده و پاسخ به نظرات مشتریان
- داشبورد با آمار

## پشتیبانی

در صورت بروز مشکل، لطفاً از طریق Issues گیت‌هاب مطرح کنید.

---

# Arcave - Online Marketplace Platform

## Quick Setup

**To run the application, please execute the `setup.sh` file:**

```bash
chmod +x setup.sh
./setup.sh
```

## Prerequisites

- Python 3.8 or higher
- PostgreSQL
- pip

## Manual Setup

If you prefer manual installation:

### 1. Create Virtual Environment
```bash
python3 -m venv venv
source venv/bin/activate  # macOS/Linux
# or
venv\Scripts\activate  # Windows
```

### 2. Install Dependencies
```bash
pip install -r requirements.txt
```

### 3. Database Setup
```bash
# Create database in PostgreSQL
psql -U postgres
CREATE DATABASE arcave_db;
\q
```

### 4. Run Migrations
```bash
python manage.py makemigrations
python manage.py migrate
```

### 5. Run Server
```bash
python manage.py runserver
```

The application will be available at `http://127.0.0.1:8000`.

## Features

### Customer Features:
- User registration and login
- Browse and search products
- Purchase products
- Leave reviews on purchased products
- View purchase history

### Shop Owner Features:
- Store registration with security questions
- Add products with images
- Manage products
- View and reply to customer reviews
- Dashboard with statistics

## Support

If you encounter any issues, please open an issue on GitHub.
