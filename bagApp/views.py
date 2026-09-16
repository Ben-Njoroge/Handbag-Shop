from django.shortcuts import render, get_object_or_404, redirect
from django.db.models import Q
from django.contrib import messages
from .models import Product, Cart, CartItem, Order, OrderItem, ShippingLocation, ContactMessage, Category
from django.db.models import Case, When, Value, BooleanField
from django.http import JsonResponse


def home(request):
    categories = Category.objects.all()

    # Sort all products: 1st by Sale status (True first), 2nd by Newest
    all_products = Product.objects.annotate(
        is_sale=Case(
            When(old_price__isnull=False, then=Value(True)),
            default=Value(False),
            output_field=BooleanField(),
        )
    ).order_by('-is_sale', '-id')

    context = {
        'categories': categories,
        'all_products': all_products,
    }
    return render(request, 'bagApp/home.html', context)

def product_list(request):
    # Start with all products
    products = Product.objects.all()
    categories = Category.objects.all()

    # 1. Search Bar Logic
    query = request.GET.get('q')
    if query:
        products = products.filter(
            Q(name__icontains=query) | Q(description__icontains=query) | Q(category__name__icontains=query)
        )

    # 2. Category Filter
    category_slug = request.GET.get('category')
    if category_slug:
        products = products.filter(category__slug=category_slug)

    # 3. Color Filter
    color = request.GET.get('color')
    if color:
        products = products.filter(color_group=color)

    # 4. Price Bracket Filter
    min_price = request.GET.get('min_price')
    max_price = request.GET.get('max_price')
    if min_price:
        products = products.filter(price__gte=min_price)
    if max_price:
        products = products.filter(price__lte=max_price)

    # 5. Sorting
    sort_by = request.GET.get('sort')
    if sort_by == 'price_low':
        products = products.order_by('price')
    elif sort_by == 'price_high':
        products = products.order_by('-price')
    else:
        products = products.order_by('-id')  # Default: Newest first

    context = {
        'products': products,
        'categories': categories,
        'color_choices': Product.COLOR_CHOICES, # Send color options to HTML
    }
    return render(request, 'bagApp/product_list.html', context)

def product_detail(request, pk):
    # 'pk' stands for Primary Key (the unique ID of the product)
    product = get_object_or_404(Product, pk=pk)
    return render(request, 'bagApp/product_detail.html', {'product': product})


def _cart_id(request):
    cart = request.session.session_key
    if not cart:
        cart = request.session.create()
    return cart


# 2. The main logic to add a handbag to the cart
def add_to_cart(request, product_id):
    product = get_object_or_404(Product, id=product_id)
    is_ajax = request.headers.get('x-requested-with') == 'XMLHttpRequest'

    # Helper function to calculate cart total
    def get_cart_count(current_cart):
        if not current_cart:
            return 0
        return sum(item.quantity for item in CartItem.objects.filter(cart=current_cart))

    # 1. Block if completely out of stock
    if product.stock_quantity <= 0:
        msg = f"Sorry, the {product.name} is completely out of stock."
        if is_ajax:
            # Try to get the cart just to send the current count back
            try:
                cart = Cart.objects.get(cart_id=_cart_id(request))
                count = get_cart_count(cart)
            except Cart.DoesNotExist:
                count = 0
            return JsonResponse({'status': 'error', 'message': msg, 'cart_count': count})

        messages.error(request, msg)
        current_page = request.META.get('HTTP_REFERER')
        return redirect(current_page) if current_page else redirect('product_list')

    # Get or create cart
    try:
        cart = Cart.objects.get(cart_id=_cart_id(request))
    except Cart.DoesNotExist:
        cart = Cart.objects.create(cart_id=_cart_id(request))
        cart.save()

    try:
        cart_item = CartItem.objects.get(product=product, cart=cart)
        # 2. Check stock limit
        if cart_item.quantity < product.stock_quantity:
            cart_item.quantity += 1
            cart_item.save()
            msg = f"Updated {product.name} quantity in your cart."
            if is_ajax:
                return JsonResponse({'status': 'success', 'message': msg, 'cart_count': get_cart_count(cart)})
            messages.success(request, msg)
        else:
            msg = f"You can only add a maximum of {product.stock_quantity} for {product.name}."
            if is_ajax:
                return JsonResponse({'status': 'warning', 'message': msg, 'cart_count': get_cart_count(cart)})
            messages.warning(request, msg)

    except CartItem.DoesNotExist:
        # 3. Create new cart item
        if product.stock_quantity > 0:
            cart_item = CartItem.objects.create(
                product=product,
                quantity=1,
                cart=cart,
            )
            cart_item.save()
            msg = f"Added {product.name} to your cart."
            if is_ajax:
                return JsonResponse({'status': 'success', 'message': msg, 'cart_count': get_cart_count(cart)})
            messages.success(request, msg)

    # Fallback
    current_page = request.META.get('HTTP_REFERER')
    if current_page:
        return redirect(current_page)
    return redirect('product_list')
# 3. A placeholder view for the actual cart page so our redirect doesn't crash
def cart_detail(request):
    total = 0
    cart_items = None

    try:
        # Get the cart using the browser session ID
        cart = Cart.objects.get(cart_id=_cart_id(request))
        # Fetch all active items inside that cart
        cart_items = CartItem.objects.filter(cart=cart, is_active=True)

        # Calculate the total price of everything in the cart
        for cart_item in cart_items:
            total += (cart_item.product.price * cart_item.quantity)

    except Cart.DoesNotExist:
        # If the cart doesn't exist, it simply means it is empty
        pass

    # Send the data to the HTML template
    context = {
        'total': total,
        'cart_items': cart_items,
    }
    return render(request, 'bagApp/cart_detail.html', context)

def remove_cart_item(request, product_id):
    # This decreases the quantity by 1
    cart = Cart.objects.get(cart_id=_cart_id(request))
    product = get_object_or_404(Product, id=product_id)
    try:
        cart_item = CartItem.objects.get(product=product, cart=cart)
        if cart_item.quantity > 1:
            cart_item.quantity -= 1
            cart_item.save()
        else:
            cart_item.delete()
    except CartItem.DoesNotExist:
        pass
    return redirect('cart_detail')

def remove_cart_item_completely(request, product_id):
    # This deletes the entire item from the cart immediately
    cart = Cart.objects.get(cart_id=_cart_id(request))
    product = get_object_or_404(Product, id=product_id)
    try:
        cart_item = CartItem.objects.get(product=product, cart=cart)
        cart_item.delete()
    except CartItem.DoesNotExist:
        pass
    return redirect('cart_detail')


def checkout(request):
    try:
        cart = Cart.objects.get(cart_id=_cart_id(request))
        cart_items = CartItem.objects.filter(cart=cart, is_active=True)
    except Cart.DoesNotExist:
        return redirect('product_list')

    if not cart_items:
        return redirect('product_list')

    cart_total = sum(item.product.price * item.quantity for item in cart_items)
    locations = ShippingLocation.objects.all().order_by('category', 'name')

    if request.method == 'POST':
        location_id = request.POST.get('delivery_location')
        shipping_location = ShippingLocation.objects.get(id=location_id)

        grand_total = cart_total + shipping_location.price

        order = Order.objects.create(
            full_name=request.POST.get('full_name'),
            phone_number=request.POST.get('phone_number'),
            delivery_location=shipping_location,
            delivery_notes=request.POST.get('delivery_notes'),
            delivery_fee_paid=shipping_location.price,
            mpesa_receipt_code=request.POST.get('mpesa_code').upper(),
            total_amount=grand_total
        )

        for item in cart_items:
            OrderItem.objects.create(
                order=order, product=item.product, price=item.product.price, quantity=item.quantity
            )

        cart_items.delete()
        messages.success(request, 'Your order was received! You can track it here.')
        return redirect('track_order')

    return render(request, 'bagApp/checkout.html',
                  {'cart_items': cart_items, 'cart_total': cart_total, 'locations': locations})


def track_order(request):
    order = None
    error = None

    if request.method == 'POST':
        phone = request.POST.get('phone_number')
        mpesa = request.POST.get('mpesa_code').upper()

        try:
            order = Order.objects.get(phone_number=phone, mpesa_receipt_code=mpesa)
        except Order.DoesNotExist:
            error = "We couldn't find an order with that Phone Number and M-PESA code."

    return render(request, 'bagApp/track_order.html', {'order': order, 'error': error})


def contact(request):
    if request.method == 'POST':
        ContactMessage.objects.create(
            name=request.POST.get('name'),
            email=request.POST.get('email'),
            subject=request.POST.get('subject'),
            message=request.POST.get('message')
        )
        messages.success(request, 'Thank you! Your message has been sent successfully.')
        return redirect('contact')

    return render(request, 'bagApp/contact.html')