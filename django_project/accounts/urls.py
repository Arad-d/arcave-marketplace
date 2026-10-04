from django.urls import path
from . import views

urlpatterns = [
    path('', views.landing, name='landing'),
    path('customer/signup/', views.customer_signup, name='customer_signup'),
    path('customer/login/', views.customer_login, name='customer_login'),
    path('customer/edit-profile/', views.edit_customer_profile, name='edit_customer_profile'),
    path('shop-owner/signup/', views.shop_owner_signup, name='shop_owner_signup'),
    path('shop-owner/login/', views.shop_owner_login, name='shop_owner_login'),
    path('shop-owner/edit-profile/', views.edit_shop_owner_profile, name='edit_shop_owner_profile'),
    path('forgot-password/', views.forgot_password, name='forgot_password'),
    path('forgot-password/customer/', views.verify_customer_security, name='verify_customer_security'),
    path('forgot-password/shop-owner/', views.verify_shop_owner_security, name='verify_shop_owner_security'),
    path('reset-password/<str:user_type>/<int:user_id>/', views.reset_password, name='reset_password'),
    path('logout/', views.logout_view, name='logout'),
]
