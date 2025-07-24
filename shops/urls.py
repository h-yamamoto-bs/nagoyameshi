from django.urls import path
from . import views

app_name = 'shops'

urlpatterns = [
    path('shop_list/', views.ShopListView.as_view(), name='shop_list'),
    path('shop_<int:pk>/', views.ShopDetailView.as_view(), name='shop_detail'),
    path('search/', views.ShopSearchView.as_view(), name='search'),
]
