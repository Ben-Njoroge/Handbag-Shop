from django.contrib import admin
from django.utils.html import format_html
from .models import Product, Cart, CartItem, Order, OrderItem, ShippingLocation, ContactMessage, Category


admin.site.register(Cart)
admin.site.register(CartItem)

@admin.register(ShippingLocation)
class ShippingLocationAdmin(admin.ModelAdmin):
    list_display = ['name', 'category', 'price', 'requires_waybill']
    list_filter = ['category']

class OrderItemInline(admin.TabularInline):
    model = OrderItem
    readonly_fields = ('price', 'quantity', 'product')
    extra = 0

@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = ['id', 'full_name', 'delivery_location','delivery_notes', 'tracking_number', 'status', 'created_at']
    list_editable = ['status', 'tracking_number']
    list_filter = ['status', 'created_at']
    inlines = [OrderItemInline]

    def save_model(self, request, obj, form, change):
        if change:
            old_order = Order.objects.get(pk=obj.pk)
            # Deduct stock ONLY when manually changed from Pending to Paid
            if old_order.status == 'Pending' and obj.status == 'Paid':
                for item in obj.items.all():
                    item.product.stock_quantity -= item.quantity
                    item.product.save()
        super().save_model(request, obj, form, change)
class StockStatusFilter(admin.SimpleListFilter):
    title = 'Stock Level'
    parameter_name = 'stock_status'

    def lookups(self, request, model_admin):
        return (
            ('out', 'Out of Stock (0)'),
            ('low', 'Low Stock (1 to 3)'),
            ('in_stock', 'Healthy Stock (4+)'),
        )

    def queryset(self, request, queryset):
        if self.value() == 'out':
            return queryset.filter(stock_quantity=0)
        if self.value() == 'low':
            return queryset.filter(stock_quantity__gte=1, stock_quantity__lte=3)
        if self.value() == 'in_stock':
            return queryset.filter(stock_quantity__gt=3)
        return queryset


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    # Added category, is_trending, and is_popular to the display
    list_display = ['name', 'category', 'price', 'stock_quantity', 'is_trending', 'is_popular', 'inventory_status']

    # Now you can check the trending/popular boxes right from the main list!
    list_editable = ['stock_quantity', 'price', 'is_trending', 'is_popular']

    # Added category and color_group to the right-side filters
    list_filter = ['category', 'color_group', StockStatusFilter, 'is_trending', 'is_popular']

    search_fields = ['name']

    # The custom function for the color-coded traffic light system
    # The custom function for the color-coded traffic light system
    def inventory_status(self, obj):
        if obj.stock_quantity <= 0:
            return format_html(
                '<span style="color: white; background-color: red; padding: 3px 8px; border-radius: 4px; font-weight: bold;">{}</span>',
                'Out of Stock'
            )
        elif obj.stock_quantity <= 3:
            return format_html(
                '<span style="color: white; background-color: orange; padding: 3px 8px; border-radius: 4px; font-weight: bold;">{}</span>',
                'Low Stock'
            )
        return format_html(
            '<span style="color: green; font-weight: bold;">{}</span>',
            'Good'
        )

    inventory_status.short_description = 'Status'

@admin.register(ContactMessage)
class ContactMessageAdmin(admin.ModelAdmin):
    list_display = ['name', 'email', 'subject', 'created_at']
    search_fields = ['name', 'email', 'subject']
    list_filter = ['created_at']

@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ['name', 'slug']
    prepopulated_fields = {'slug': ('name',)}