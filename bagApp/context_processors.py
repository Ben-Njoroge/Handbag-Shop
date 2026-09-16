from .models import Cart, CartItem,Product, Category


def search_suggestions(request):
    # Fetch 3 trending and 3 popular products for the search dropdown
    return {
        'suggested_trending': Product.objects.filter(is_trending=True)[:3],
        'suggested_popular': Product.objects.filter(is_popular=True)[:3],
        'nav_categories': Category.objects.all()
    }

def cart_counter(request):
    cart_count = 0

    # We don't need to count items if the user is in the Django Admin panel
    if 'admin' in request.path:
        return {}

    try:
        # Securely grab the session key without forcing a new session creation
        session_key = request.session.session_key
        if session_key:
            cart = Cart.objects.get(cart_id=session_key)
            cart_items = CartItem.objects.filter(cart=cart)

            # Loop through the items and add their quantities together
            for cart_item in cart_items:
                cart_count += cart_item.quantity
    except Cart.DoesNotExist:
        cart_count = 0

    # This dictionary broadcasts the 'cart_count' variable to all HTML files
    return dict(cart_count=cart_count)