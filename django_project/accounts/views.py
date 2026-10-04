from django.shortcuts import render, redirect
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.hashers import make_password
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db import connection
from django.utils import timezone
from datetime import timedelta
from .models import Customer, ShopOwner


# Helper functions for account lockout
def is_account_locked(user):
    """Check if account is currently locked."""
    if user.locked_until and timezone.now() < user.locked_until:
        remaining = int((user.locked_until - timezone.now()).total_seconds())
        return True, remaining
    return False, 0


def lock_account(user):
    """Lock account for 5 minutes."""
    user.locked_until = timezone.now() + timedelta(minutes=5)
    user.failed_attempts = 0
    user.save()


def record_failed_attempt(user):
    """Record failed attempt and lock if 2 failures reached."""
    user.failed_attempts += 1
    if user.failed_attempts >= 2:
        lock_account(user)
    else:
        user.save()


def clear_failed_attempts(user):
    """Clear failed attempts after successful login."""
    user.failed_attempts = 0
    user.locked_until = None
    user.save()


def landing(request):
    """Landing page with login/signup options."""
    return render(request, 'accounts/landing.html')


def customer_signup(request):
    """Customer registration view."""
    if request.method == 'POST':
        username = request.POST.get('username')
        email = request.POST.get('email')
        password = request.POST.get('password')
        password2 = request.POST.get('password2')
        security_question1 = request.POST.get('security_question1')
        security_answer1 = request.POST.get('security_answer1')
        security_question2 = request.POST.get('security_question2')
        security_answer2 = request.POST.get('security_answer2')
        
        if password != password2:
            messages.error(request, 'رمزهای عبور مطابقت ندارند.')
            return render(request, 'accounts/customer_signup.html')
        
        if Customer.objects.filter(username=username).exists():
            messages.error(request, 'این نام کاربری قبلاً ثبت شده است.')
            return render(request, 'accounts/customer_signup.html')
        
        if Customer.objects.filter(email=email).exists():
            messages.error(request, 'این ایمیل قبلاً ثبت شده است.')
            return render(request, 'accounts/customer_signup.html')
        
        customer = Customer.objects.create_user(
            username=username,
            email=email,
            password=password
        )
        
        # Save security questions (convert answers to lowercase for case-insensitive comparison)
        customer.security_question1 = security_question1
        customer.security_answer1 = security_answer1.lower() if security_answer1 else ''
        customer.security_question2 = security_question2
        customer.security_answer2 = security_answer2.lower() if security_answer2 else ''
        customer.save()
        
        messages.success(request, 'حساب کاربری با موفقیت ایجاد شد! لطفاً وارد شوید.')
        return redirect('customer_login')
    
    return render(request, 'accounts/customer_signup.html')


def customer_login(request):
    """Customer login view."""
    if request.method == 'POST':
        username = request.POST.get('username')
        password = request.POST.get('password')
        
        # Check if account exists and is locked
        try:
            customer = Customer.objects.get(username=username)
            locked, remaining = is_account_locked(customer)
            if locked:
                minutes = remaining // 60
                seconds = remaining % 60
                messages.error(request, f'حساب کاربری قفل شده است. لطفاً پس از {minutes}:{seconds:02d} دوباره تلاش کنید.')
                return render(request, 'accounts/customer_login.html')
        except Customer.DoesNotExist:
            pass
        
        user = authenticate(request, username=username, password=password)
        
        if user is not None:
            # Clear failed attempts on successful login
            try:
                customer = Customer.objects.get(username=username)
                clear_failed_attempts(customer)
            except Customer.DoesNotExist:
                pass
            login(request, user)
            return redirect('customer_dashboard')
        else:
            # Record failed attempt
            try:
                customer = Customer.objects.get(username=username)
                record_failed_attempt(customer)
                locked, remaining = is_account_locked(customer)
                if locked:
                    minutes = remaining // 60
                    seconds = remaining % 60
                    messages.error(request, f'تلاش‌های ناموفق زیاد. حساب کاربری برای {minutes}:{seconds:02d} قفل شده است.')
                else:
                    messages.error(request, 'نام کاربری یا رمز عبور اشتباه است.')
            except Customer.DoesNotExist:
                messages.error(request, 'نام کاربری یا رمز عبور اشتباه است.')
    
    return render(request, 'accounts/customer_login.html')


def shop_owner_signup(request):
    """Shop owner registration view."""
    if request.method == 'POST':
        name = request.POST.get('name')
        store_name = request.POST.get('store_name')
        password = request.POST.get('password')
        password2 = request.POST.get('password2')
        address = request.POST.get('address')
        phone = request.POST.get('phone')
        security_question1 = request.POST.get('security_question1')
        security_answer1 = request.POST.get('security_answer1')
        security_question2 = request.POST.get('security_question2')
        security_answer2 = request.POST.get('security_answer2')
        
        if password != password2:
            messages.error(request, 'رمزهای عبور مطابقت ندارند.')
            return render(request, 'accounts/shop_owner_signup.html')
        
        if ShopOwner.objects.filter(name=name).exists():
            messages.error(request, 'این نام قبلاً ثبت شده است.')
            return render(request, 'accounts/shop_owner_signup.html')
        
        # Using Django ORM to create shop owner with automatic timestamp
        ShopOwner.objects.create(
            name=name,
            store_name=store_name,
            password=make_password(password),
            address=address,
            phone=phone,
            security_question1=security_question1,
            security_answer1=security_answer1,
            security_question2=security_question2,
            security_answer2=security_answer2,
            role=1
        )
        
        messages.success(request, 'حساب فروشنده با موفقیت ایجاد شد! لطفاً وارد شوید.')
        return redirect('shop_owner_login')
    
    return render(request, 'accounts/shop_owner_signup.html')


def shop_owner_login(request):
    """Shop owner login view."""
    if request.method == 'POST':
        name = request.POST.get('name')
        password = request.POST.get('password')
        
        # Check if account exists and is locked
        try:
            shop_owner = ShopOwner.objects.get(name=name)
            locked, remaining = is_account_locked(shop_owner)
            if locked:
                minutes = remaining // 60
                seconds = remaining % 60
                messages.error(request, f'حساب کاربری قفل شده است. لطفاً پس از {minutes}:{seconds:02d} دوباره تلاش کنید.')
                return render(request, 'accounts/shop_owner_login.html')
        except ShopOwner.DoesNotExist:
            pass
        
        try:
            shop_owner = ShopOwner.objects.get(name=name)
            if not shop_owner.check_password(password):
                raise ShopOwner.DoesNotExist
            # Clear failed attempts on successful login
            clear_failed_attempts(shop_owner)
            # Store shop owner ID in session
            request.session['shop_owner_id'] = shop_owner.id
            request.session['shop_owner_name'] = shop_owner.name
            request.session['shop_owner_store'] = shop_owner.store_name
            return redirect('shop_owner_dashboard')
        except ShopOwner.DoesNotExist:
            # Record failed attempt
            try:
                shop_owner = ShopOwner.objects.get(name=name)
                record_failed_attempt(shop_owner)
                locked, remaining = is_account_locked(shop_owner)
                if locked:
                    minutes = remaining // 60
                    seconds = remaining % 60
                    messages.error(request, f'تلاش‌های ناموفق زیاد. حساب کاربری برای {minutes}:{seconds:02d} قفل شده است.')
                else:
                    messages.error(request, 'نام یا رمز عبور اشتباه است.')
            except ShopOwner.DoesNotExist:
                messages.error(request, 'نام یا رمز عبور اشتباه است.')
    
    return render(request, 'accounts/shop_owner_login.html')


def logout_view(request):
    """Logout view for both customer and shop owner."""
    logout(request)
    # Clear shop owner session if exists
    if 'shop_owner_id' in request.session:
        del request.session['shop_owner_id']
        del request.session['shop_owner_name']
        del request.session['shop_owner_store']
    return redirect('landing')


@login_required
def edit_customer_profile(request):
    """Edit customer profile - username cannot be changed."""
    customer = request.user
    
    if request.method == 'POST':
        email = request.POST.get('email')
        current_password = request.POST.get('current_password')
        new_password = request.POST.get('new_password')
        confirm_password = request.POST.get('confirm_password')
        
        # Update email
        if email and email != customer.email:
            if Customer.objects.filter(email=email).exclude(pk=customer.pk).exists():
                messages.error(request, 'این ایمیل قبلاً ثبت شده است.')
                return render(request, 'accounts/edit_customer_profile.html', {'customer': customer})
            customer.email = email
        
        # Update password if provided
        if current_password and new_password:
            if not customer.check_password(current_password):
                messages.error(request, 'رمز عبور فعلی اشتباه است.')
                return render(request, 'accounts/edit_customer_profile.html', {'customer': customer})
            
            if new_password != confirm_password:
                messages.error(request, 'رمزهای عبور جدید مطابقت ندارند.')
                return render(request, 'accounts/edit_customer_profile.html', {'customer': customer})
            
            customer.set_password(new_password)
            messages.success(request, 'رمز عبور با موفقیت به‌روزرسانی شد! لطفاً دوباره وارد شوید.')
            customer.save()
            logout(request)
            return redirect('customer_login')
        
        customer.save()
        messages.success(request, 'پروفایل با موفقیت به‌روزرسانی شد!')
        return redirect('customer_dashboard')
    
    return render(request, 'accounts/edit_customer_profile.html', {'customer': customer})


def edit_shop_owner_profile(request):
    """Edit shop owner profile - name (username) cannot be changed."""
    shop_owner_id = request.session.get('shop_owner_id')
    
    if not shop_owner_id:
        messages.error(request, 'لطفاً به عنوان فروشنده وارد شوید.')
        return redirect('shop_owner_login')
    
    try:
        shop_owner = ShopOwner.objects.get(id=shop_owner_id)
    except ShopOwner.DoesNotExist:
        messages.error(request, 'فروشنده یافت نشد.')
        return redirect('shop_owner_login')
    
    if request.method == 'POST':
        store_name = request.POST.get('store_name')
        address = request.POST.get('address')
        phone = request.POST.get('phone')
        current_password = request.POST.get('current_password')
        new_password = request.POST.get('new_password')
        confirm_password = request.POST.get('confirm_password')
        
        # Update profile info
        if store_name:
            shop_owner.store_name = store_name
        shop_owner.address = address
        shop_owner.phone = phone
        
        # Update password if provided
        if current_password and new_password:
            if not shop_owner.check_password(current_password):
                messages.error(request, 'رمز عبور فعلی اشتباه است.')
                return render(request, 'accounts/edit_shop_owner_profile.html', {'shop_owner': shop_owner})
            
            if new_password != confirm_password:
                messages.error(request, 'رمزهای عبور جدید مطابقت ندارند.')
                return render(request, 'accounts/edit_shop_owner_profile.html', {'shop_owner': shop_owner})
            
            shop_owner.set_password(new_password)
            messages.success(request, 'رمز عبور با موفقیت به‌روزرسانی شد! لطفاً دوباره وارد شوید.')
            shop_owner.save()
            logout(request)
            # Clear session
            if 'shop_owner_id' in request.session:
                del request.session['shop_owner_id']
                del request.session['shop_owner_name']
                del request.session['shop_owner_store']
            return redirect('shop_owner_login')
        
        shop_owner.save()
        # Update session store name
        request.session['shop_owner_store'] = shop_owner.store_name
        messages.success(request, 'پروفایل با موفقیت به‌روزرسانی شد!')
        return redirect('shop_owner_dashboard')
    return render(request, 'accounts/edit_shop_owner_profile.html', {'shop_owner': shop_owner})


def forgot_password(request):
    """Forgot password selection page."""
    return render(request, 'accounts/forgot_password.html')


def verify_customer_security(request):
    """Verify customer security questions."""
    step = request.session.get('security_step', 1)
    customer_id = request.session.get('reset_customer_id')
    
    if request.method == 'POST':
        if 'username' in request.POST:
            # Step 1: Get username and check account
            username = request.POST.get('username')
            try:
                customer = Customer.objects.get(username=username)
                
                # Check if account is locked
                locked, remaining = is_account_locked(customer)
                if locked:
                    minutes = remaining // 60
                    seconds = remaining % 60
                    messages.error(request, f'Account is locked. Please try again in {minutes}:{seconds:02d}.')
                    return render(request, 'accounts/verify_customer_security.html', {
                        'step': 1,
                        'locked': True,
                        'remaining': remaining
                    })
                
                # Store customer ID and show first question
                request.session['reset_customer_id'] = customer.id
                request.session['security_step'] = 2
                return render(request, 'accounts/verify_customer_security.html', {
                    'step': 2,
                    'question': customer.security_question1
                })
            except Customer.DoesNotExist:
                messages.error(request, 'Username not found.')
                return render(request, 'accounts/verify_customer_security.html', {'step': 1})
        
        elif 'answer1' in request.POST:
            # Step 2: Verify first answer
            answer = request.POST.get('answer1', '').lower().strip()
            try:
                customer = Customer.objects.get(id=customer_id)
                
                # Check if account is locked
                locked, remaining = is_account_locked(customer)
                if locked:
                    minutes = remaining // 60
                    seconds = remaining % 60
                    messages.error(request, f'Account is locked. Please try again in {minutes}:{seconds:02d}.')
                    return render(request, 'accounts/verify_customer_security.html', {
                        'step': 1,
                        'locked': True,
                        'remaining': remaining
                    })
                
                if answer == customer.security_answer1:
                    # Correct! Allow password reset
                    request.session['verified_for_reset'] = True
                    request.session['reset_user_type'] = 'customer'
                    request.session['verified_reset_user_id'] = customer.id
                    return redirect('reset_password', user_type='customer', user_id=customer.id)
                else:
                    # Wrong answer, show second question
                    messages.error(request, 'Incorrect answer. Second question:')
                    request.session['security_step'] = 3
                    return render(request, 'accounts/verify_customer_security.html', {
                        'step': 3,
                        'question': customer.security_question2
                    })
            except Customer.DoesNotExist:
                messages.error(request, 'Error verifying security question.')
                return redirect('forgot_password')
        
        elif 'answer2' in request.POST:
            # Step 3: Verify second answer
            answer = request.POST.get('answer2', '').lower().strip()
            try:
                customer = Customer.objects.get(id=customer_id)
                
                if answer == customer.security_answer2:
                    # Correct! Allow password reset
                    request.session['verified_for_reset'] = True
                    request.session['reset_user_type'] = 'customer'
                    request.session['verified_reset_user_id'] = customer.id
                    return redirect('reset_password', user_type='customer', user_id=customer.id)
                else:
                    # Both answers wrong - lock account
                    record_failed_attempt(customer)
                    lock_account(customer)
                    messages.error(request, 'Both security answers were incorrect. Account locked for 5 minutes.')
                    return render(request, 'accounts/verify_customer_security.html', {
                        'step': 1,
                        'locked': True,
                        'remaining': 300
                    })
            except Customer.DoesNotExist:
                messages.error(request, 'Error verifying security question.')
                return redirect('forgot_password')
    
    # GET request
    if step == 2 and customer_id:
        try:
            customer = Customer.objects.get(id=customer_id)
            locked, remaining = is_account_locked(customer)
            if locked:
                return render(request, 'accounts/verify_customer_security.html', {
                    'step': 1,
                    'locked': True,
                    'remaining': remaining
                })
            return render(request, 'accounts/verify_customer_security.html', {
                'step': 2,
                'question': customer.security_question1
            })
        except Customer.DoesNotExist:
            pass
    elif step == 3 and customer_id:
        try:
            customer = Customer.objects.get(id=customer_id)
            return render(request, 'accounts/verify_customer_security.html', {
                'step': 3,
                'question': customer.security_question2
            })
        except Customer.DoesNotExist:
            pass
    
    # Reset session and show username form
    request.session.pop('security_step', None)
    request.session.pop('reset_customer_id', None)
    return render(request, 'accounts/verify_customer_security.html', {'step': 1})


def verify_shop_owner_security(request):
    """Verify shop owner security questions."""
    step = request.session.get('shop_security_step', 1)
    shop_owner_id = request.session.get('reset_shop_owner_id')
    
    if request.method == 'POST':
        if 'name' in request.POST:
            # Step 1: Get name and check account
            name = request.POST.get('name')
            try:
                shop_owner = ShopOwner.objects.get(name=name)
                
                # Check if account is locked
                locked, remaining = is_account_locked(shop_owner)
                if locked:
                    minutes = remaining // 60
                    seconds = remaining % 60
                    messages.error(request, f'Account is locked. Please try again in {minutes}:{seconds:02d}.')
                    return render(request, 'accounts/verify_shop_owner_security.html', {
                        'step': 1,
                        'locked': True,
                        'remaining': remaining
                    })
                
                # Store shop owner ID and show first question
                request.session['reset_shop_owner_id'] = shop_owner.id
                request.session['shop_security_step'] = 2
                return render(request, 'accounts/verify_shop_owner_security.html', {
                    'step': 2,
                    'question': shop_owner.security_question1
                })
            except ShopOwner.DoesNotExist:
                messages.error(request, 'Name not found.')
                return render(request, 'accounts/verify_shop_owner_security.html', {'step': 1})
        
        elif 'answer1' in request.POST:
            # Step 2: Verify first answer
            answer = request.POST.get('answer1', '').lower().strip()
            try:
                shop_owner = ShopOwner.objects.get(id=shop_owner_id)
                
                # Check if account is locked
                locked, remaining = is_account_locked(shop_owner)
                if locked:
                    minutes = remaining // 60
                    seconds = remaining % 60
                    messages.error(request, f'Account is locked. Please try again in {minutes}:{seconds:02d}.')
                    return render(request, 'accounts/verify_shop_owner_security.html', {
                        'step': 1,
                        'locked': True,
                        'remaining': remaining
                    })
                
                if answer == shop_owner.security_answer1.lower():
                    # Correct! Allow password reset
                    request.session['verified_for_reset'] = True
                    request.session['reset_user_type'] = 'shop_owner'
                    request.session['verified_reset_user_id'] = shop_owner.id
                    return redirect('reset_password', user_type='shop_owner', user_id=shop_owner.id)
                else:
                    # Wrong answer, show second question
                    messages.error(request, 'Incorrect answer. Second question:')
                    request.session['shop_security_step'] = 3
                    return render(request, 'accounts/verify_shop_owner_security.html', {
                        'step': 3,
                        'question': shop_owner.security_question2
                    })
            except ShopOwner.DoesNotExist:
                messages.error(request, 'Error verifying security question.')
                return redirect('forgot_password')
        
        elif 'answer2' in request.POST:
            # Step 3: Verify second answer
            answer = request.POST.get('answer2', '').lower().strip()
            try:
                shop_owner = ShopOwner.objects.get(id=shop_owner_id)
                
                if answer == shop_owner.security_answer2.lower():
                    # Correct! Allow password reset
                    request.session['verified_for_reset'] = True
                    request.session['reset_user_type'] = 'shop_owner'
                    request.session['verified_reset_user_id'] = shop_owner.id
                    return redirect('reset_password', user_type='shop_owner', user_id=shop_owner.id)
                else:
                    # Both answers wrong - lock account
                    record_failed_attempt(shop_owner)
                    lock_account(shop_owner)
                    messages.error(request, 'Both security answers were incorrect. Account locked for 5 minutes.')
                    return render(request, 'accounts/verify_shop_owner_security.html', {
                        'step': 1,
                        'locked': True,
                        'remaining': 300
                    })
            except ShopOwner.DoesNotExist:
                messages.error(request, 'Error verifying security question.')
                return redirect('forgot_password')
    
    # GET request
    if step == 2 and shop_owner_id:
        try:
            shop_owner = ShopOwner.objects.get(id=shop_owner_id)
            locked, remaining = is_account_locked(shop_owner)
            if locked:
                return render(request, 'accounts/verify_shop_owner_security.html', {
                    'step': 1,
                    'locked': True,
                    'remaining': remaining
                })
            return render(request, 'accounts/verify_shop_owner_security.html', {
                'step': 2,
                'question': shop_owner.security_question1
            })
        except ShopOwner.DoesNotExist:
            pass
    elif step == 3 and shop_owner_id:
        try:
            shop_owner = ShopOwner.objects.get(id=shop_owner_id)
            return render(request, 'accounts/verify_shop_owner_security.html', {
                'step': 3,
                'question': shop_owner.security_question2
            })
        except ShopOwner.DoesNotExist:
            pass
    
    # Reset session and show name form
    request.session.pop('shop_security_step', None)
    request.session.pop('reset_shop_owner_id', None)
    return render(request, 'accounts/verify_shop_owner_security.html', {'step': 1})


def reset_password(request, user_type, user_id):
    """Reset password after successful security verification."""
    # Verify that user came from security verification
    if not request.session.get('verified_for_reset'):
        messages.error(request, 'Please verify your identity first.')
        return redirect('forgot_password')
    
    # Verify user type matches
    if (
        user_type not in {'customer', 'shop_owner'}
        or request.session.get('reset_user_type') != user_type
        or request.session.get('verified_reset_user_id') != user_id
    ):
        messages.error(request, 'Invalid reset request.')
        return redirect('forgot_password')
    
    if request.method == 'POST':
        new_password = request.POST.get('new_password')
        confirm_password = request.POST.get('confirm_password')
        
        if not new_password:
            messages.error(request, 'Please enter a new password.')
            return render(request, 'accounts/reset_password.html', {'user_type': user_type})
        
        if new_password != confirm_password:
            messages.error(request, 'Passwords do not match.')
            return render(request, 'accounts/reset_password.html', {'user_type': user_type})
        
        # Update password based on user type
        if user_type == 'customer':
            try:
                customer = Customer.objects.get(id=user_id)
                customer.set_password(new_password)
                clear_failed_attempts(customer)
                customer.save()
                messages.success(request, 'Password reset successfully! Please log in.')
                
                # Clear session
                request.session.pop('verified_for_reset', None)
                request.session.pop('verified_reset_user_id', None)
                request.session.pop('reset_user_type', None)
                request.session.pop('reset_customer_id', None)
                request.session.pop('security_step', None)
                
                return redirect('customer_login')
            except Customer.DoesNotExist:
                messages.error(request, 'Error resetting password.')
                return redirect('forgot_password')
        
        elif user_type == 'shop_owner':
            try:
                shop_owner = ShopOwner.objects.get(id=user_id)
                shop_owner.set_password(new_password)
                clear_failed_attempts(shop_owner)
                shop_owner.save()
                messages.success(request, 'Password reset successfully! Please log in.')
                
                # Clear session
                request.session.pop('verified_for_reset', None)
                request.session.pop('verified_reset_user_id', None)
                request.session.pop('reset_user_type', None)
                request.session.pop('reset_shop_owner_id', None)
                request.session.pop('shop_security_step', None)
                
                return redirect('shop_owner_login')
            except ShopOwner.DoesNotExist:
                messages.error(request, 'Error resetting password.')
                return redirect('forgot_password')
    
    return render(request, 'accounts/reset_password.html', {'user_type': user_type})
