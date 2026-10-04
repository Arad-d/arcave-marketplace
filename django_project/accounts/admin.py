from django.contrib import admin
from .models import Customer, ShopOwner


@admin.register(Customer)
class CustomerAdmin(admin.ModelAdmin):
    list_display = ['username', 'email', 'created_at']
    search_fields = ['username', 'email']
    list_filter = ['created_at']


@admin.register(ShopOwner)
class ShopOwnerAdmin(admin.ModelAdmin):
    list_display = ['name', 'store_name', 'created_at']
    search_fields = ['name', 'store_name']
    list_filter = ['created_at']
