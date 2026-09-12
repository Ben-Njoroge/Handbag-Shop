from django.shortcuts import render
from .models import Product

def product_list(request):
    # Fetch all products, newest first
    products = Product.objects.all().order_by('-created_at')
    return render(request, 'bagApp/product_list.html', {'products': products})