from django.shortcuts import render
from .models import Shop
from django.views.generic import ListView

class ShopListView(ListView):
    model = Shop
    template_name = 'shops/shop_list.html'
    context_object_name = 'shops'