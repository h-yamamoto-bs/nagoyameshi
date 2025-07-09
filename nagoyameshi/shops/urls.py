from django.urls import path
from . import views

app_name = 'shops'

urlpatterns = [
    path('base/', views.ShopListView.as_view(), name='base'),
]
