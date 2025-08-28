from functools import wraps
from django.shortcuts import redirect
from django.http import JsonResponse
from django.urls import reverse
from .models import Subscription
from .utils import sync_subscription_from_stripe


def subscription_required(view_func):
    """サブスクリプション会員のみ許可するデコレータ。
    - 未契約/無効の場合:
      - 通常リクエスト: マイページ(サブスク管理)へリダイレクト
      - AJAXリクエスト: 200 JSON を返し、redirect_url を通知（ネットワークエラー回避）
    実行直前にStripeと同期して最新状態を反映。
    """
    @wraps(view_func)
    def _wrapped(request, *args, **kwargs):
        def is_ajax(req):
            return req.headers.get('x-requested-with') == 'XMLHttpRequest'

        redirect_url = reverse('accounts:mypage') + '?err=subscription_required'

        if not request.user.is_authenticated:
            if is_ajax(request):
                return JsonResponse({
                    'success': False,
                    'message': 'ログインが必要です。',
                    'redirect_url': reverse('accounts:login')
                }, status=200)
            return redirect('accounts:login')

        # 実行前に同期して最新化
        try:
            sync_subscription_from_stripe(request.user)
        except Exception:
            pass

        try:
            subscription = request.user.subscription
        except Subscription.DoesNotExist:
            if is_ajax(request):
                return JsonResponse({
                    'success': False,
                    'message': 'プレミアム会員限定の機能です。サブスクリプションをご契約ください。',
                    'redirect_url': redirect_url
                }, status=200)
            return redirect(redirect_url)

        has_valid_stripe_subscription = bool(getattr(subscription, 'stripe_subscription_id', None))
        if not (getattr(subscription, 'is_active', False) and has_valid_stripe_subscription):
            if is_ajax(request):
                return JsonResponse({
                    'success': False,
                    'message': 'サブスクリプションが無効です。マイページからご確認ください。',
                    'redirect_url': redirect_url
                }, status=200)
            return redirect(redirect_url)

        return view_func(request, *args, **kwargs)

    return _wrapped
