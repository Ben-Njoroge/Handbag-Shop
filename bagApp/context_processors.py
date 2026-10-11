from .models import Cart, CartItem, Product, Category, WishlistItem, Wishlist, SearchHistory


def search_suggestions(request):
    # Base context for the search dropdown
    context = {
        'suggested_trending': Product.objects.filter(is_trending=True)[:3],
        'suggested_popular': Product.objects.filter(is_popular=True)[:3],
        'nav_categories': Category.objects.all(),
        'recent_searches': []
    }

    # If the user is logged in, fetch their 5 most recent searches
    if request.user.is_authenticated:
        context['recent_searches'] = SearchHistory.objects.filter(user=request.user)[:5]

    return context


def cart_counter(request):
    cart_count = 0

    if 'admin' in request.path:
        return {}

    try:
        cart = None
        # 1. Check if user is logged in
        if request.user.is_authenticated:
            cart = Cart.objects.filter(user=request.user).first()
        # 2. Fall back to guest session
        else:
            session_key = request.session.session_key
            if session_key:
                cart = Cart.objects.filter(cart_id=session_key).first()

        # 3. Calculate total items
        if cart:
            cart_items = CartItem.objects.filter(cart=cart)
            for cart_item in cart_items:
                cart_count += cart_item.quantity

    except Exception:
        cart_count = 0

    return dict(cart_count=cart_count)


def wishlist_counter(request):
    wishlist_count = 0

    if 'admin' in request.path:
        return {}

    try:
        wishlist = None
        # 1. Check if user is logged in
        if request.user.is_authenticated:
            wishlist = Wishlist.objects.filter(user=request.user).first()
        # 2. Fall back to guest session
        else:
            session_id = request.session.session_key
            if not session_id:
                request.session.create()
                session_id = request.session.session_key
            wishlist = Wishlist.objects.filter(wishlist_id=session_id).first()

        # 3. Count active wishlist items
        if wishlist:
            wishlist_count = WishlistItem.objects.filter(wishlist=wishlist, is_active=True).count()

    except Exception:
        wishlist_count = 0

    return dict(wishlist_count=wishlist_count)