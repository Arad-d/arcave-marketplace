from django.contrib.auth.models import AbstractUser
from django.db import models


class Customer(AbstractUser):
    """Customer user model with basic authentication and security questions."""
    
    email = models.EmailField(unique=True)
    security_question1 = models.CharField(max_length=255, blank=True, null=True)
    security_answer1 = models.CharField(max_length=255, blank=True, null=True)
    security_question2 = models.CharField(max_length=255, blank=True, null=True)
    security_answer2 = models.CharField(max_length=255, blank=True, null=True)
    failed_attempts = models.IntegerField(default=0)
    locked_until = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'customers'
    
    def __str__(self):
        return self.username


class ShopOwner(models.Model):
    """Shop owner model with security questions as per original CLI app."""
    
    name = models.CharField(max_length=100)
    store_name = models.CharField(max_length=200)
    password = models.CharField(max_length=128)
    security_question1 = models.CharField(max_length=255)
    security_answer1 = models.CharField(max_length=255)
    security_question2 = models.CharField(max_length=255)
    security_answer2 = models.CharField(max_length=255)
    role = models.IntegerField(default=1)
    address = models.TextField(blank=True, null=True, help_text='Shop address')
    phone = models.CharField(max_length=20, blank=True, null=True, help_text='Phone number with country code (e.g., +989123456789)')
    failed_attempts = models.IntegerField(default=0)
    locked_until = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'shop_owners'
    
    def __str__(self):
        return f"{self.name} - {self.store_name}"
