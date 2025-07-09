from django.shortcuts import render
from .models import User
from django.views.generic import ListView

class AccountListView(ListView):
    model = User
    template_name = 'accounts/account_list.html'
    context_object_name = 'users'