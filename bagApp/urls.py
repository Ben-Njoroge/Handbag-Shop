from django.urls import path
from . import views

urlpatterns = [
    path('', views.home, name='home'),
    path('shop/', views.product_list, name='product_list'),
    # This captures the ID from the URL and passes it to the view
    path('product/<int:pk>/', views.product_detail, name='product_detail'),
    path('cart/add/<int:product_id>/', views.add_to_cart, name='add_to_cart'),
    path('cart/', views.cart_detail, name='cart_detail'),
    path('cart/remove/<int:product_id>/', views.remove_cart_item, name='remove_cart_item'),
    path('cart/delete/<int:product_id>/', views.remove_cart_item_completely, name='remove_cart_item_completely'),
    path('checkout/', views.checkout, name='checkout'),
    path('track/', views.track_order, name='track_order'),
    path('contact/', views.contact, name='contact'),
]