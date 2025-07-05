from django.urls import path
from . import views

app_name = 'shops'

urlpatterns = [
    path('shop_list/', views.shop_list, name='shop_list'),
]
