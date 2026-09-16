from django.db import models
from django.utils.text import slugify

class Category(models.Model):
    name = models.CharField(max_length=100)
    slug = models.SlugField(max_length=100, unique=True, blank=True)
    image = models.ImageField(upload_to='categories/', blank=True, null=True, help_text="Circular image for the homepage")

    class Meta:
        verbose_name_plural = 'Categories'

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)
        super().save(*args, **kwargs)

    def __str__(self):
        return self.name

class Product(models.Model):
    name = models.CharField(max_length=200)
    description = models.TextField()
    price = models.DecimalField(max_digits=10, decimal_places=2)
    stock_quantity = models.PositiveIntegerField(default=1)
    image =  models.ImageField(upload_to='handbags/')
    created_at = models.DateTimeField(auto_now_add=True)

    # 1. The Category Link
    category = models.ForeignKey(Category, related_name='products', on_delete=models.SET_NULL, null=True, blank=True)

    # 2. The Color Filter Choices
    COLOR_CHOICES = [
        ('Blacks/Greys', '⚫ Blacks & Greys'),
        ('Browns/Tans', '🟤 Browns & Tans'),
        ('Whites/Creams', '⚪ Whites & Creams'),
        ('Brights/Bolds', '🔴 Brights & Bolds'),
        ('Other', '✨ Other Colors')
    ]
    color_group = models.CharField(max_length=50, choices=COLOR_CHOICES, default='Blacks/Greys')

    # 3. Marketing & Sales
    old_price = models.DecimalField(max_digits=10, decimal_places=2, blank=True, null=True,
                                    help_text="Set this to show a strike-through price and a SALE badge.")
    is_trending = models.BooleanField(default=False,
                                      help_text="Check this to show the bag in the 'Trending' section on the homepage.")
    is_popular = models.BooleanField(default=False, help_text="Check this to feature the bag in the 'Popular' section.")

    def __str__(self):
        return f"{self.name} - KES{self.price}"
class Cart(models.Model):
    # This will store the browser's unique session key
    cart_id = models.CharField(max_length=250, blank=True)
    date_added = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.cart_id

class CartItem(models.Model):
    # Links the item to a specific handbag and a specific cart
    product = models.ForeignKey(Product, on_delete=models.CASCADE)
    cart = models.ForeignKey(Cart, on_delete=models.CASCADE)
    quantity = models.IntegerField(default=1)
    is_active = models.BooleanField(default=True)

    # A quick helper function to calculate the price * quantity
    def sub_total(self):
        return self.product.price * self.quantity

    def __str__(self):
        return self.product.name


class ShippingLocation(models.Model):
    CATEGORY_CHOICES = (
        ('Local', 'Within Nyeri Town (Free Meetup)'),
        ('2NK', '2NK Parcel Services'),
        ('Other', 'Other Arrangements (Call to Agree)'),
    )

    name = models.CharField(max_length=100)
    price = models.DecimalField(max_digits=6, decimal_places=2, default=0.00)
    category = models.CharField(max_length=20, choices=CATEGORY_CHOICES, default='2NK')
    requires_waybill = models.BooleanField(default=True, help_text="True for 2NK, False for Meetups/Riders")

    def __str__(self):
        if self.price == 0:
            return f"{self.name} - Free / TBD"
        return f"{self.name} - KES {self.price}"


class Order(models.Model):
    STATUS_CHOICES = (
        ('Pending', 'Pending'),
        ('Paid', 'Paid'),
        ('Dispatched', 'Dispatched'),
        ('Delivered', 'Delivered'),
        ('Cancelled', 'Cancelled'),
    )

    full_name = models.CharField(max_length=100)
    phone_number = models.CharField(max_length=20)

    # Link to our new shipping system
    delivery_location = models.ForeignKey(ShippingLocation, on_delete=models.SET_NULL, null=True)
    delivery_notes = models.CharField(max_length=255, blank=True, null=True,
                                      help_text="Customer's exact town and transport choice")
    delivery_fee_paid = models.DecimalField(max_digits=6, decimal_places=2, default=0.00)
    tracking_number = models.CharField(max_length=100, blank=True, null=True, help_text="2NK Waybill Number")

    mpesa_receipt_code = models.CharField(max_length=20, unique=True)
    total_amount = models.DecimalField(max_digits=10, decimal_places=2)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='Pending')
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Order #{self.id} - {self.full_name}"


# Make sure you still have your OrderItem model here!

class OrderItem(models.Model):
    # Link the item to the order and the specific product
    order = models.ForeignKey(Order, related_name='items', on_delete=models.CASCADE)
    product = models.ForeignKey(Product, on_delete=models.CASCADE)
    price = models.DecimalField(max_digits=10, decimal_places=2)
    quantity = models.IntegerField(default=1)

    def __str__(self):
        return f"{self.quantity} x {self.product.name}"

class ContactMessage(models.Model):
    name = models.CharField(max_length=100)
    email = models.EmailField()
    subject = models.CharField(max_length=200)
    message = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Message from {self.name} - {self.subject}"