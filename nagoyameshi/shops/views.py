from django.shortcuts import render
from .models import Shop
from django.views.generic import ListView

# Create your views here.
class ShopListView(ListView):
    model = Shop
    template_name = 'shops/base.html'
    context_object_name = 'shops'