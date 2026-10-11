from django.shortcuts import render, get_object_or_404, redirect
from django.db.models import Q
from django.contrib import messages
from .models import Product, Cart, CartItem, Order, OrderItem, ShippingLocation, ContactMessage, Category, Wishlist, \
    WishlistItem, UserProfile, SearchHistory, Review
from django.db.models import Case, When, Value, BooleanField
from django.http import JsonResponse
from django.core.mail import send_mail, EmailMessage
from django.conf import settings
from django.contrib.auth import login, logout, authenticate
from django.contrib.auth.forms import AuthenticationForm
from .forms import UserRegistrationForm
from django.contrib.auth.decorators import login_required
from django.db.models import Avg


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
    products = Product.objects.all()
    categories = Category.objects.all()

    # 1. Search Bar Logic + Personalization
    query = request.GET.get('q')
    if query:
        products = products.filter(
            Q(name__icontains=query) | Q(description__icontains=query) | Q(category__name__icontains=query)
        )

        # Save Search History (Rolling Cap of 5)
        if request.user.is_authenticated:
            SearchHistory.objects.create(user=request.user, query=query)
            old_searches = SearchHistory.objects.filter(user=request.user).order_by('-created_at')[5:]
            for old_search in old_searches:
                old_search.delete()

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
        products = products.order_by('-id')

    context = {
        'products': products,
        'categories': categories,
        'color_choices': Product.COLOR_CHOICES,
    }
    return render(request, 'bagApp/product_list.html', context)


def product_detail(request, slug):
    product = get_object_or_404(Product, slug=slug)
    reviews = product.reviews.all()

    # 1. Calculate Review Count and Average Rating
    review_count = reviews.count()
    avg_rating_raw = reviews.aggregate(Avg('rating'))['rating__avg']
    avg_rating = round(avg_rating_raw, 1) if avg_rating_raw else 0.0
    avg_rating_int = int(round(avg_rating))  # Used to color the correct number of stars

    can_review = False
    if request.user.is_authenticated:
        has_purchased = OrderItem.objects.filter(
            order__user=request.user,
            order__status='Completed',
            product=product
        ).exists()

        has_reviewed = Review.objects.filter(user=request.user, product=product).exists()

        if has_purchased and not has_reviewed:
            can_review = True

    context = {
        'product': product,
        'reviews': reviews,
        'review_count': review_count,
        'avg_rating': avg_rating,
        'avg_rating_int': avg_rating_int,
        'can_review': can_review
    }
    return render(request, 'bagApp/product_detail.html', context)
def submit_review(request, product_id):
    if request.method == 'POST' and request.user.is_authenticated:
        product = get_object_or_404(Product, id=product_id)

        # Double-check security: ensure they actually bought it and it is Completed
        valid_purchase = OrderItem.objects.filter(
            order__user=request.user,
            order__status='Completed',
            product=product
        ).exists()

        if valid_purchase:
            rating = request.POST.get('rating', 5)
            text = request.POST.get('text', '')

            Review.objects.create(
                user=request.user,
                product=product,
                rating=rating,
                text=text
            )
            messages.success(request, "Thank you! Your review has been posted.")
        else:
            messages.error(request, "You can only review products from completed orders.")

    return redirect('product_detail', pk=product_id)

# --- CART LOGIC ---

def _cart_id(request):
    cart = request.session.session_key
    if not cart:
        cart = request.session.create()
    return cart


def add_to_cart(request, product_id):
    product = get_object_or_404(Product, id=product_id)
    is_ajax = request.headers.get('x-requested-with') == 'XMLHttpRequest'

    def get_cart_count(current_cart):
        if not current_cart:
            return 0
        return sum(item.quantity for item in CartItem.objects.filter(cart=current_cart))

    # Dual Identity Check
    if request.user.is_authenticated:
        cart, _ = Cart.objects.get_or_create(user=request.user)
    else:
        cart, _ = Cart.objects.get_or_create(cart_id=_cart_id(request))

    if product.stock_quantity <= 0:
        msg = f"Sorry, the {product.name} is completely out of stock."
        if is_ajax:
            return JsonResponse({'status': 'error', 'message': msg, 'cart_count': get_cart_count(cart)})

        messages.error(request, msg)
        current_page = request.META.get('HTTP_REFERER')
        return redirect(current_page) if current_page else redirect('product_list')

    requested_quantity = 1
    action = 'add_to_cart'

    if request.method == 'POST':
        try:
            requested_quantity = int(request.POST.get('quantity', 1))
        except ValueError:
            requested_quantity = 1
        action = request.POST.get('submit_action', 'add_to_cart')

    try:
        cart_item = CartItem.objects.get(product=product, cart=cart)
        if (cart_item.quantity + requested_quantity) <= product.stock_quantity:
            cart_item.quantity += requested_quantity
            cart_item.save()
            msg = f"Updated {product.name} quantity in your cart."

            if action == 'buy_now':
                return redirect('cart_detail')

            if is_ajax:
                return JsonResponse({'status': 'success', 'message': msg, 'cart_count': get_cart_count(cart)})
            messages.success(request, msg)
        else:
            msg = f"You can only add a maximum of {product.stock_quantity} for {product.name}."
            if is_ajax:
                return JsonResponse({'status': 'warning', 'message': msg, 'cart_count': get_cart_count(cart)})
            messages.warning(request, msg)

    except CartItem.DoesNotExist:
        if requested_quantity <= product.stock_quantity:
            cart_item = CartItem.objects.create(
                product=product,
                quantity=requested_quantity,
                cart=cart,
            )
            msg = f"Added {product.name} to your cart."

            if action == 'buy_now':
                return redirect('cart_detail')

            if is_ajax:
                return JsonResponse({'status': 'success', 'message': msg, 'cart_count': get_cart_count(cart)})
            messages.success(request, msg)
        else:
            msg = f"You can only add a maximum of {product.stock_quantity} for {product.name}."
            if is_ajax:
                return JsonResponse({'status': 'warning', 'message': msg, 'cart_count': get_cart_count(cart)})
            messages.warning(request, msg)

    if action == 'buy_now':
        return redirect('cart_detail')

    current_page = request.META.get('HTTP_REFERER')
    if current_page:
        return redirect(current_page)
    return redirect('product_list')


def cart_detail(request):
    total = 0
    cart_items = None
    counter = 0

    try:
        if request.user.is_authenticated:
            cart = Cart.objects.filter(user=request.user).first()
        else:
            cart = Cart.objects.filter(cart_id=_cart_id(request)).first()

        if cart:
            cart_items = CartItem.objects.filter(cart=cart, is_active=True)
            for cart_item in cart_items:
                total += (cart_item.product.price * cart_item.quantity)
                counter += cart_item.quantity
    except Exception:
        pass

    context = {
        'total': total,
        'cart_items': cart_items,
        'counter': counter,
    }
    return render(request, 'bagApp/cart_detail.html', context)


def remove_cart_item(request, product_id):
    product = get_object_or_404(Product, id=product_id)
    try:
        if request.user.is_authenticated:
            cart = Cart.objects.get(user=request.user)
        else:
            cart = Cart.objects.get(cart_id=_cart_id(request))

        cart_item = CartItem.objects.get(product=product, cart=cart)
        if cart_item.quantity > 1:
            cart_item.quantity -= 1
            cart_item.save()
        else:
            cart_item.delete()
    except (Cart.DoesNotExist, CartItem.DoesNotExist):
        pass
    return redirect('cart_detail')


def remove_cart_item_completely(request, product_id):
    product = get_object_or_404(Product, id=product_id)
    try:
        if request.user.is_authenticated:
            cart = Cart.objects.get(user=request.user)
        else:
            cart = Cart.objects.get(cart_id=_cart_id(request))

        cart_item = CartItem.objects.get(product=product, cart=cart)
        cart_item.delete()
    except (Cart.DoesNotExist, CartItem.DoesNotExist):
        pass
    return redirect('cart_detail')


# --- CHECKOUT LOGIC ---

def checkout(request):
    try:
        if request.user.is_authenticated:
            cart = Cart.objects.get(user=request.user)
        else:
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
            user=request.user if request.user.is_authenticated else None,  # Attach user if logged in
            full_name=request.POST.get('full_name'),
            phone_number=request.POST.get('phone_number'),
            delivery_location=shipping_location,
            delivery_notes=request.POST.get('delivery_notes'),
            delivery_fee_paid=shipping_location.price,
            mpesa_receipt_code=request.POST.get('mpesa_code').upper(),
            total_amount=grand_total
        )

        items_ordered_text = ""
        for item in cart_items:
            OrderItem.objects.create(
                order=order, product=item.product, price=item.product.price, quantity=item.quantity
            )
            items_ordered_text += f"- {item.quantity}x {item.product.name} (KES {item.product.price})\n"

        cart_items.delete()

        # Email Alert
        subject = f'🚨 NEW ORDER: KES {order.total_amount} via M-Pesa'
        message = f"""
You just received a new order!

CUSTOMER DETAILS
Name: {order.full_name}
Phone: {order.phone_number}
Location: {shipping_location.name}
Notes: {order.delivery_notes if order.delivery_notes else 'None'}

ORDER SUMMARY
{items_ordered_text}
Delivery Fee: KES {order.delivery_fee_paid}
Total Amount: KES {order.total_amount}

M-PESA VERIFICATION
Code: {order.mpesa_receipt_code}
"""
        try:
            send_mail(
                subject, message, settings.DEFAULT_FROM_EMAIL, [settings.DEFAULT_FROM_EMAIL], fail_silently=True
            )
        except Exception as e:
            print(f"Email failed to send: {e}")

        messages.success(request, 'Your order was received! You can track it here.')
        return redirect('track_order')

    return render(request, 'bagApp/checkout.html',
                  {'cart_items': cart_items, 'cart_total': cart_total, 'locations': locations})


def track_order(request):
    order = None
    error = None
    active_orders = None

    # 1. If logged in, fetch their active orders automatically (excluding cancelled ones)
    if request.user.is_authenticated:
        active_orders = Order.objects.filter(
            user=request.user
        ).exclude(status='Cancelled').order_by('-created_at')

    # 2. Manual lookup logic for guests
    if request.method == 'POST':
        phone = request.POST.get('phone_number')
        mpesa = request.POST.get('mpesa_code').upper()

        try:
            order = Order.objects.get(phone_number=phone, mpesa_receipt_code=mpesa)
        except Order.DoesNotExist:
            error = "We couldn't find an order with that Phone Number and M-PESA code."

    return render(request, 'bagApp/track_order.html', {
        'order': order,
        'error': error,
        'active_orders': active_orders
    })
def contact(request):
    if request.method == 'POST':
        name = request.POST.get('name')
        customer_email = request.POST.get('email')
        subject_line = request.POST.get('subject')
        message_text = request.POST.get('message')

        ContactMessage.objects.create(
            name=name, email=customer_email, subject=subject_line, message=message_text
        )

        email_subject = f"NEW WEBSITE MESSAGE: {subject_line}"
        email_body = f"Name: {name}\nEmail: {customer_email}\n\nMESSAGE\n{message_text}"

        try:
            email = EmailMessage(
                subject=email_subject, body=email_body, from_email=settings.DEFAULT_FROM_EMAIL,
                to=[settings.DEFAULT_FROM_EMAIL], reply_to=[customer_email]
            )
            email.send(fail_silently=True)
        except Exception as e:
            print(f"Contact email failed to send: {e}")

        messages.success(request, 'Thank you! Your message has been sent successfully.')
        return redirect('contact')

    return render(request, 'bagApp/contact.html')


# --- WISHLIST LOGIC ---

def _wishlist_id(request):
    wishlist_id = request.session.session_key
    if not wishlist_id:
        wishlist_id = request.session.create()
    return wishlist_id


def add_to_wishlist(request, product_id):
    product = get_object_or_404(Product, id=product_id)
    is_ajax = request.headers.get('x-requested-with') == 'XMLHttpRequest'

    def get_wishlist_count(current_wishlist):
        if not current_wishlist:
            return 0
        return WishlistItem.objects.filter(wishlist=current_wishlist, is_active=True).count()

    if request.user.is_authenticated:
        wishlist, _ = Wishlist.objects.get_or_create(user=request.user)
    else:
        wishlist, _ = Wishlist.objects.get_or_create(wishlist_id=_wishlist_id(request))

    try:
        wishlist_item = WishlistItem.objects.get(product=product, wishlist=wishlist)
        msg = f"{product.name} is already in your wishlist."

        if is_ajax:
            return JsonResponse({'status': 'warning', 'message': msg, 'wishlist_count': get_wishlist_count(wishlist)})
        messages.warning(request, msg)

    except WishlistItem.DoesNotExist:
        WishlistItem.objects.create(product=product, wishlist=wishlist)
        msg = f"Added {product.name} to your wishlist."

        if is_ajax:
            return JsonResponse({'status': 'success', 'message': msg, 'wishlist_count': get_wishlist_count(wishlist)})
        messages.success(request, msg)

    current_page = request.META.get('HTTP_REFERER')
    return redirect(current_page) if current_page else redirect('product_list')


def wishlist_detail(request):
    try:
        if request.user.is_authenticated:
            wishlist = Wishlist.objects.get(user=request.user)
        else:
            wishlist = Wishlist.objects.get(wishlist_id=_wishlist_id(request))
        wishlist_items = WishlistItem.objects.filter(wishlist=wishlist, is_active=True).order_by('-date_added')
    except Wishlist.DoesNotExist:
        wishlist_items = None

    return render(request, 'bagApp/wishlist.html', {'wishlist_items': wishlist_items})


def remove_from_wishlist(request, product_id):
    product = get_object_or_404(Product, id=product_id)
    try:
        if request.user.is_authenticated:
            wishlist = Wishlist.objects.get(user=request.user)
        else:
            wishlist = Wishlist.objects.get(wishlist_id=_wishlist_id(request))

        wishlist_item = WishlistItem.objects.get(product=product, wishlist=wishlist)
        wishlist_item.delete()
        messages.success(request, f"Removed {product.name} from your wishlist.")
    except (Wishlist.DoesNotExist, WishlistItem.DoesNotExist):
        pass

    return redirect('wishlist')


# --- AUTH LOGIC ---

def merge_session_data_to_user(request, user):
    session_cart_id = request.session.session_key

    if session_cart_id:
        try:
            session_cart = Cart.objects.get(cart_id=session_cart_id)
            user_cart, _ = Cart.objects.get_or_create(user=user)

            session_items = CartItem.objects.filter(cart=session_cart)
            for item in session_items:
                user_item = CartItem.objects.filter(cart=user_cart, product=item.product).first()
                if user_item:
                    user_item.quantity = min(user_item.quantity + item.quantity, item.product.stock_quantity)
                    user_item.save()
                    item.delete()
                else:
                    item.cart = user_cart
                    item.save()

            session_cart.delete()
        except Cart.DoesNotExist:
            pass

    if session_cart_id:
        try:
            session_wishlist = Wishlist.objects.get(wishlist_id=session_cart_id)
            user_wishlist, _ = Wishlist.objects.get_or_create(user=user)

            session_wishlist_items = WishlistItem.objects.filter(wishlist=session_wishlist)
            for w_item in session_wishlist_items:
                if not WishlistItem.objects.filter(wishlist=user_wishlist, product=w_item.product).exists():
                    w_item.wishlist = user_wishlist
                    w_item.save()
                else:
                    w_item.delete()

            session_wishlist.delete()
        except Wishlist.DoesNotExist:
            pass


def register_user(request):
    if request.user.is_authenticated:
        return redirect('product_list')

    if request.method == 'POST':
        form = UserRegistrationForm(request.POST)
        if form.is_valid():
            user = form.save(commit=False)
            user.username = form.cleaned_data['email']
            user.set_password(form.cleaned_data['password'])
            user.save()

            UserProfile.objects.create(user=user)
            login(request, user)
            merge_session_data_to_user(request, user)

            messages.success(request, f"Welcome to the Handbag Collection, {user.first_name}!")
            return redirect('product_list')
    else:
        form = UserRegistrationForm()

    return render(request, 'bagApp/register.html', {'form': form})


def login_user(request):
    if request.user.is_authenticated:
        return redirect('product_list')

    if request.method == 'POST':
        form = AuthenticationForm(request, data=request.POST)
        if form.is_valid():
            username = form.cleaned_data.get('username')
            password = form.cleaned_data.get('password')
            user = authenticate(username=username, password=password)

            if user is not None:
                login(request, user)
                merge_session_data_to_user(request, user)
                messages.success(request, f"Welcome back, {user.first_name}!")

                next_page = request.GET.get('next', 'product_list')
                return redirect(next_page)
        else:
            messages.error(request, "Invalid email or password.")
    else:
        form = AuthenticationForm()

    return render(request, 'bagApp/login.html', {'form': form})


def logout_user(request):
    logout(request)
    messages.info(request, "You have been logged out successfully.")
    return redirect('product_list')


@login_required(login_url='login')
def user_dashboard(request):
    # Fetch all orders belonging to this specific user, newest first
    orders = Order.objects.filter(user=request.user).order_by('-created_at')

    context = {
        'orders': orders,
    }
    return render(request, 'bagApp/dashboard.html', context)