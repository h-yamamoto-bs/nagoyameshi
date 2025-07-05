from django.urls import path
from . import views

app_name = 'accounts'

urlpatterns = [
    path('account_list/', views.account_list, name='account_list'),
]
