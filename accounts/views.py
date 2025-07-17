from django.shortcuts import render
from .models import User
from django.views.generic import ListView, TemplateView

class AccountListView(ListView):
    model = User
    template_name = 'accounts/account_list.html'
    context_object_name = 'users'

class LoginView(TemplateView):
    template_name = 'accounts/login.html'

class RegisterView(TemplateView):
    template_name = 'accounts/register.html'