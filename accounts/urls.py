from django.urls import path
from . import views

app_name = 'accounts'

urlpatterns = [
    path('account_list/', views.AccountListView.as_view(), name='account_list'),
    path('login/', views.LoginView.as_view(), name='login'),
    path('register/', views.RegisterView.as_view(), name='register'),
    path('logout/', views.logout_view, name='logout'),
]
