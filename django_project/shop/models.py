from django.db import models
from accounts.models import Customer, ShopOwner


class Product(models.Model):
    """Product/commodity model with inventory tracking."""

    CATEGORY_CHOICES = [
        ('electronics', 'محصولات الکترونیک'),
        ('accessories', 'لوازم جانبی الکترونیک'),
    ]

    shop_owner = models.ForeignKey(ShopOwner, on_delete=models.CASCADE, related_name='products')
    name = models.CharField(max_length=200)
    price = models.DecimalField(max_digits=10, decimal_places=2)
    description = models.TextField()
    image = models.ImageField(upload_to='products/', blank=True, null=True)
    stock = models.PositiveIntegerField(default=0, help_text='Number of units available')
    category = models.CharField(max_length=20, choices=CATEGORY_CHOICES, default='electronics')
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'products'
        ordering = ['-created_at']
    
    def __str__(self):
        return self.name
    
    def is_in_stock(self):
        return self.stock > 0
    
    def has_enough_stock(self, quantity):
        return self.stock >= quantity


class Cart(models.Model):
    """Shopping cart for customers."""
    
    customer = models.ForeignKey(Customer, on_delete=models.CASCADE, related_name='cart_items')
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='cart_entries')
    quantity = models.PositiveIntegerField(default=1)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'cart'
        unique_together = ['customer', 'product']
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.customer.username} - {self.product.name} x{self.quantity}"
    
    def get_total_price(self):
        return self.product.price * self.quantity


class Comment(models.Model):
    """Customer comments on products."""
    
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='comments')
    customer = models.ForeignKey(Customer, on_delete=models.CASCADE, related_name='comments')
    text = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'comments'
        ordering = ['-created_at']
    
    def __str__(self):
        return f"Comment by {self.customer.username} on {self.product.name}"
    
    def has_reply(self):
        return hasattr(self, 'reply')


class Reply(models.Model):
    """Shop owner replies to comments."""
    
    comment = models.OneToOneField(Comment, on_delete=models.CASCADE, related_name='reply')
    shop_owner = models.ForeignKey(ShopOwner, on_delete=models.CASCADE, related_name='replies')
    text = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'replies'
        ordering = ['-created_at']
    
    def __str__(self):
        return f"Reply by {self.shop_owner.store_name}"


class Purchase(models.Model):
    """Customer purchases of products with quantity."""
    
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='purchases')
    customer = models.ForeignKey(Customer, on_delete=models.CASCADE, related_name='purchases')
    quantity = models.PositiveIntegerField(default=1)
    total_price = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'purchases'
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.customer.username} bought {self.quantity}x {self.product.name}"
