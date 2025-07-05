from django.shortcuts import render
from .models import User
from django.views.generic import ListView

# Create your views here.
class AccountListView(ListView):
    model = User
    template_name = 'accounts/base.html'
    context_object_name = 'users'