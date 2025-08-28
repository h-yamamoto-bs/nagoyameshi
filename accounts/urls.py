from django.urls import path
from . import views
from .webhooks import stripe_webhook

app_name = 'accounts'

urlpatterns = [
    path('account_list/', views.AccountListView.as_view(), name='account_list'),
    path('login/', views.LoginView.as_view(), name='login'),
    path('register/', views.RegisterView.as_view(), name='register'),
    path('logout/', views.logout_view, name='logout'),
    path('mypage/', views.MyPageView.as_view(), name='mypage'),
    path('profile/update/', views.update_profile, name='update_profile'),
    path('subscription/update/', views.update_subscription, name='update_subscription'),
    path('subscription/cancel/', views.cancel_subscription, name='cancel_subscription'),
    path('pay/', views.PayWithStripeView.as_view(), name='pay_with_stripe'),
    path('pay/success/', views.PaySuccessView.as_view(), name='pay_success'),
    path('pay/cancel/', views.PayCancelView.as_view(), name='pay_cancel'),
    path('subscription/portal/', views.StripeBillingPortalView.as_view(), name='subscription_portal'),
    path('stripe/webhook/', stripe_webhook, name='stripe_webhook'),
]
