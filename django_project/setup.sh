#!/bin/bash

# Arcave Setup Script
# This script sets up the Arcave Django application

set -e  # Exit on error

echo "=========================================="
echo "    خوش آمدید به نصب‌کننده آرکیو"
echo "    Welcome to Arcave Setup"
echo "=========================================="
echo ""

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Function to print colored messages
print_success() {
    echo -e "${GREEN}✓ $1${NC}"
}

print_error() {
    echo -e "${RED}✗ $1${NC}"
}

print_info() {
    echo -e "${YELLOW}→ $1${NC}"
}

# Check if Python is installed
print_info "بررسی نصب پایتون..."
if ! command -v python3 &> /dev/null; then
    print_error "پایتون ۳ نصب نشده است. لطفاً ابتدا پایتون را نصب کنید."
    print_error "Python 3 is not installed. Please install Python 3 first."
    exit 1
fi

PYTHON_VERSION=$(python3 --version 2>&1 | awk '{print $2}')
print_success "پایتون نسخه $PYTHON_VERSION یافت شد"

# Check Python version (need 3.8+)
REQUIRED_VERSION="3.8"
if ! python3 -c "import sys; exit(0 if sys.version_info >= (3, 8) else 1)" 2>/dev/null; then
    print_error "نیاز به پایتون ۳.۸ یا بالاتر دارید"
    print_error "Python 3.8 or higher is required"
    exit 1
fi

# Check if pip is installed
print_info "بررسی نصب pip..."
if ! command -v pip3 &> /dev/null; then
    print_error "pip نصب نشده است"
    print_error "pip is not installed"
    exit 1
fi
print_success "pip یافت شد"

# Check if PostgreSQL is installed
print_info "بررسی نصب PostgreSQL..."
if ! command -v psql &> /dev/null; then
    print_error "PostgreSQL نصب نشده است"
    print_error "PostgreSQL is not installed"
    echo ""
    echo "برای نصب PostgreSQL:"
    echo "macOS: brew install postgresql"
    echo "Ubuntu/Debian: sudo apt-get install postgresql"
    echo "Windows: https://www.postgresql.org/download/windows/"
    exit 1
fi
print_success "PostgreSQL یافت شد"

# Get the project directory
PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$PROJECT_DIR"

# Create virtual environment
print_info "ایجاد محیط مجازی..."
if [ -d "venv" ]; then
    print_info "محیط مجازی قبلاً وجود دارد"
else
    python3 -m venv venv
    print_success "محیط مجازی ایجاد شد"
fi

# Activate virtual environment
print_info "فعال‌سازی محیط مجازی..."
source venv/bin/activate
print_success "محیط مجازی فعال شد"

# Upgrade pip
print_info "به‌روزرسانی pip..."
pip install --upgrade pip
print_success "pip به‌روزرسانی شد"

# Install requirements
print_info "نصب وابستگی‌ها..."
if [ -f "requirements.txt" ]; then
    pip install -r requirements.txt
    print_success "وابستگی‌ها نصب شدند"
else
    print_error "فایل requirements.txt یافت نشد"
    exit 1
fi

# Create database
print_info "راه‌اندازی پایگاه داده..."
echo "لطفاً رمز عبور PostgreSQL خود را وارد کنید (اگر پیش‌فرض است، Enter بزنید):"
read -s PGPASSWORD
export PGPASSWORD

if ! psql -U postgres -lqt | cut -d \| -f 1 | grep -qw arcave_db; then
    print_info "ایجاد پایگاه داده arcave_db..."
    psql -U postgres -c "CREATE DATABASE arcave_db;" 2>/dev/null || {
        print_error "خطا در ایجاد پایگاه داده. لطفاً PostgreSQL را بررسی کنید"
        print_error "Error creating database. Please check PostgreSQL"
        exit 1
    }
    print_success "پایگاه داده ایجاد شد"
else
    print_info "پایگاه داده قبلاً وجود دارد"
fi

unset PGPASSWORD

# Create media directory
print_info "ایجاد پوشه‌های رسانه..."
mkdir -p media/products
print_success "پوشه‌های رسانه ایجاد شدند"

# Run migrations
print_info "اجرای مهاجرت‌های پایگاه داده..."
python manage.py makemigrations
python manage.py migrate
print_success "مهاجرت‌ها با موفقیت انجام شد"

# Create superuser (optional)
echo ""
echo "آیا می‌خواهید یک کاربر ادمین (سوپریوزر) ایجاد کنید؟ (y/n)"
read -r CREATE_SUPERUSER

if [[ $CREATE_SUPERUSER =~ ^[Yy]$ ]]; then
    print_info "ایجاد کاربر ادمین..."
    python manage.py createsuperuser
fi

# Success message
echo ""
echo "=========================================="
print_success "نصب با موفقیت انجام شد!"
print_success "Installation completed successfully!"
echo "=========================================="
echo ""
echo "برای اجرای سرور، دستورات زیر را اجرا کنید:"
echo "cd $PROJECT_DIR"
echo "source venv/bin/activate"
echo "python manage.py runserver"
echo ""
echo "سپس مرورگر خود را باز کنید و به آدرس زیر بروید:"
echo "http://127.0.0.1:8000"
echo ""
echo "=========================================="
