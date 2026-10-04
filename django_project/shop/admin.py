from django.contrib import admin
from .models import Product, Cart, Comment, Reply, Purchase


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ['name', 'shop_owner', 'price', 'stock', 'created_at']
    search_fields = ['name', 'description']
    list_filter = ['created_at', 'shop_owner']


@admin.register(Cart)
class CartAdmin(admin.ModelAdmin):
    list_display = ['customer', 'product', 'quantity', 'created_at']
    search_fields = ['customer__username', 'product__name']
    list_filter = ['created_at']


@admin.register(Comment)
class CommentAdmin(admin.ModelAdmin):
    list_display = ['product', 'customer', 'created_at']
    search_fields = ['text']
    list_filter = ['created_at']


@admin.register(Reply)
class ReplyAdmin(admin.ModelAdmin):
    list_display = ['comment', 'shop_owner', 'created_at']
    search_fields = ['text']
    list_filter = ['created_at']


@admin.register(Purchase)
class PurchaseAdmin(admin.ModelAdmin):
    list_display = ['product', 'customer', 'quantity', 'total_price', 'created_at']
    list_filter = ['created_at']
