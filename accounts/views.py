from django.shortcuts import render, redirect
from .models import User, Subscription
from shops.models import Favorite, Review
from django.views.generic import ListView, TemplateView, View
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.forms import AuthenticationForm
from django.contrib import messages
from django.urls import reverse_lazy
from django.views.generic import CreateView
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_POST
from django.http import JsonResponse
from django.conf import settings
import stripe
from django.utils.decorators import method_decorator
import urllib.parse
from datetime import datetime, timezone
from .utils import sync_subscription_from_stripe

# ユーザー一覧
class AccountListView(ListView):
    model = User
    template_name = 'accounts/account_list.html'
    context_object_name = 'users'

# ログイン
class LoginView(TemplateView):
    template_name = 'accounts/login.html'

    def get(self, request, *args, **kwargs):
        # ログイン画面では全メッセージをクリア（他画面のエラーを持ち込まない）
        storage = messages.get_messages(request)
        for _ in storage:
            pass
        storage.used = True
        return super().get(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['form'] = AuthenticationForm()
        return context
    
    def post(self, request, *args, **kwargs):
        # ログイン処理
        email = request.POST.get('email')
        password = request.POST.get('password')

        # ユーザー認証
        try:
            # ユーザーの存在確認
            user = User.objects.get(email=email)
            # パスワード検証
            user = authenticate(request, username=user.email, password=password)

            # 認証成功の場合
            if user is not None:
                # アカウントが有効か確認
                if user.is_active:
                    # ログイン処理
                    login(request, user)
                    messages.success(request, 'ログインしました。', extra_tags='auth')
                    # リダイレクト
                    next_url = request.GET.get('next', 'shops:shop_list')
                    return redirect('shops:shop_list')
                else:   # 無効の場合
                    messages.error(request, 'アカウントが無効です。', extra_tags='auth')
            else:  # 認証失敗
                messages.error(request, 'メールアドレスまたはパスワードが間違っています。', extra_tags='auth')
        except User.DoesNotExist:
            messages.error(request, 'このメールアドレスは登録されていません。新規登録をお試しください。', extra_tags='auth')

        # ログイン失敗時の処理
        return render(request, self.template_name, {
            'form': AuthenticationForm(),
            'email': email
        })

# 新規登録
class RegisterView(TemplateView):
    template_name = 'accounts/register.html'

    def get(self, request, *args, **kwargs):
        # 新規登録画面でも全メッセージをクリア（他画面のエラーを持ち込まない）
        storage = messages.get_messages(request)
        for _ in storage:
            pass
        storage.used = True
        return super().get(request, *args, **kwargs)

    def post(self, request, *args, **kwargs):

        # フォームからデータ取得
        email = request.POST.get('email')
        password = request.POST.get('password')
        password_confirm = request.POST.get('password_confirm')

        # 必須項目のチェック
        if not email or not password or not password_confirm:
            messages.error(request, 'すべてのフィールドを入力してください。', extra_tags='auth')
            return render(request, self.template_name, {'email': email, 'password': password, 'password_confirm': password_confirm})

        # パスワードの一致確認
        if password != password_confirm:
            messages.error(request, 'パスワードが一致しません。', extra_tags='auth')
            return render(request, self.template_name, {'email': email, 'password': password, 'password_confirm': password_confirm})

        # メールアドレス重複チェック
        if User.objects.filter(email=email).exists():
            messages.error(request, 'このメールアドレスは既に登録されています。', extra_tags='auth')
            return render(request, self.template_name, {'email': email})
        
        # ユーザー作成
        try:
            user = User.objects.create_user(
                email=email,
                password=password
            )

            # 成功メッセージ
            messages.success(request, 'アカウントが作成されました。ログインしてください。', extra_tags='auth')

            # ログインページにリダイレクト
            return redirect('accounts:login')
        
        except Exception as e:
            messages.error(request, f'アカウントの作成に失敗しました: {str(e)}', extra_tags='auth')
            return render(request, self.template_name, {'email': email})

class MyPageView(LoginRequiredMixin, TemplateView):
    template_name = 'accounts/mypage.html'
    login_url = reverse_lazy('accounts:login')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.request.user

        # 表示前に同期（解約期日経過時に自動で無効化/終了日反映）
        try:
            sync_subscription_from_stripe(user)
        except Exception:
            pass

        # サブスクリプション情報の取得
        try:
            subscription = user.subscription
        except Subscription.DoesNotExist:
            subscription = None

        # 顧客ID未保存で、CheckoutセッションIDがある場合はStripeから補完（表示直前に一度だけ試行）
        if subscription and not getattr(subscription, 'stripe_customer_id', None) and getattr(subscription, 'stripe_id', None):
            try:
                sid = str(subscription.stripe_id)
                if sid.startswith('cs_'):
                    cs = stripe.checkout.Session.retrieve(sid)
                    cust = getattr(cs, 'customer', None)
                    subid = getattr(cs, 'subscription', None)
                    updated = False
                    if cust and not subscription.stripe_customer_id:
                        subscription.stripe_customer_id = cust
                        updated = True
                    if subid and not getattr(subscription, 'stripe_subscription_id', None):
                        subscription.stripe_subscription_id = subid
                        updated = True
                    if updated:
                        subscription.save()
            except Exception:
                pass
        
        # お気に入り一覧の取得（最新5件）
        favorites = Favorite.objects.filter(user=user).select_related('shop').order_by('-id')[:5]
        
        # レビュー一覧の取得（最新5件）
        reviews = Review.objects.filter(user=user).select_related('shop').order_by('-created_at')[:5]
        
        # 統計情報
        favorite_count = Favorite.objects.filter(user=user).count()
        review_count = Review.objects.filter(user=user).count()
        
        context.update({
            'subscription': subscription,
            'favorites': favorites,
            'reviews': reviews,
            'favorite_count': favorite_count,
            'review_count': review_count,
        })
        # ここでのみStripe関連のエラーを表示
        err = self.request.GET.get('err')
        if err == 'no_subscription':
            messages.error(self.request, 'サブスクリプションの契約履歴がありません。')
        elif err == 'no_customer':
            messages.error(self.request, 'Stripeの顧客情報が未登録のため、編集画面を開けません。')
        elif err == 'portal_failed':
            messages.error(self.request, 'ポータルの起動に失敗しました。')
            # DEBUG時のみ、原因を追加表示
            reason = self.request.GET.get('reason')
            if settings.DEBUG and reason:
                messages.info(self.request, f"Stripeエラー詳細: {reason}")
        elif err == 'subscription_required':
            messages.warning(self.request, 'この機能はプレミアム会員限定です。マイページからサブスクリプションをご契約ください。')
        return context


@login_required
@require_POST
def update_profile(request):
    """プロフィール更新API"""
    try:
        user = request.user
        
        # フォームデータの取得
        email = request.POST.get('email', '').strip()
        job = request.POST.get('job', '').strip()
        birth_year = request.POST.get('birth_year', '').strip()
        
        # バリデーション
        if not email:
            return JsonResponse({
                'success': False,
                'message': 'メールアドレスは必須です。'
            }, status=400)
        
        # メールアドレスの重複チェック（自分以外）
        if User.objects.filter(email=email).exclude(pk=user.pk).exists():
            return JsonResponse({
                'success': False,
                'message': 'このメールアドレスは既に使用されています。'
            }, status=400)
        
        # 生年の検証
        if birth_year:
            try:
                birth_year = int(birth_year)
                if birth_year < 1900 or birth_year > 2025:
                    return JsonResponse({
                        'success': False,
                        'message': '生年は1900年から2025年の間で入力してください。'
                    }, status=400)
            except ValueError:
                return JsonResponse({
                    'success': False,
                    'message': '生年は数値で入力してください。'
                }, status=400)
        else:
            birth_year = None
        
        # ユーザー情報の更新
        user.email = email
        user.job = job if job else None
        user.birth_year = birth_year
        user.save()
        
        return JsonResponse({
            'success': True,
            'message': 'プロフィールが更新されました。'
        })
    
    except Exception as e:
        return JsonResponse({
            'success': False,
            'message': 'サーバーエラーが発生しました。'
        }, status=500)


@login_required
@require_POST
def update_subscription(request):
    """サブスクリプション情報更新API
    注意: 有効化はStripe決済後にのみ許可。未契約ユーザーが任意に有効化することはできない。
    無効化(停止)はユーザー操作として許可する。
    """
    try:
        user = request.user
        is_active = request.POST.get('is_active') == 'true'

        # 既存のサブスクリプションを取得（なければ None）
        try:
            subscription = Subscription.objects.get(user=user)
        except Subscription.DoesNotExist:
            subscription = None

        if is_active:
            # 有効化要求: Stripeのsubscription_idが保存されている既存契約者のみ許可
            if not subscription or not getattr(subscription, 'stripe_subscription_id', None):
                return JsonResponse({
                    'success': False,
                    'message': '有効化はStripeでのご契約完了後に自動で行われます。マイページの「プレミアム会員になる」から決済を完了してください。'
                }, status=403)
            # 既存契約者は有効化可能
            subscription.is_active = True
            subscription.save()
            return JsonResponse({'success': True, 'message': 'サブスクリプションを有効にしました。'})
        else:
            # 無効化要求: 契約の有無に関わらず許可（レコードが無ければ作成せずに成功扱いでもよい）
            if subscription:
                subscription.is_active = False
                subscription.save()
            else:
                # レコード未作成でもクライアント的には処理成功で問題ない
                pass
            return JsonResponse({'success': True, 'message': 'サブスクリプションを無効にしました。'})

    except Exception as e:
        return JsonResponse({
            'success': False,
            'message': 'サーバーエラーが発生しました。'
        }, status=500)


@login_required
@require_POST
def cancel_subscription(request):
    """サブスクリプションを今期末で解約予約する。
    - Stripeの Subscription に cancel_at_period_end=True を設定
    - ローカルの end_date を current_period_end に合わせて保存
    - すでに解約予約済みなら end_date を同期して案内
    """
    try:
        try:
            sub_model = request.user.subscription
        except Subscription.DoesNotExist:
            messages.error(request, 'サブスクリプション契約が見つかりません。')
            return redirect('accounts:mypage')

        sub_id = getattr(sub_model, 'stripe_subscription_id', None)
        if not sub_id:
            messages.error(request, 'StripeのサブスクリプションIDが見つかりません。マイページから契約状況をご確認ください。')
            return redirect('accounts:mypage')

        # Stripe上のサブスクを取得
        sub = stripe.Subscription.retrieve(sub_id)

        # すでに解約予約済みかチェック
        if getattr(sub, 'cancel_at_period_end', False):
            period_end_ts = getattr(sub, 'current_period_end', None)
            if period_end_ts:
                sub_model.end_date = datetime.fromtimestamp(period_end_ts, tz=timezone.utc).date()
                sub_model.save()
            messages.info(request, 'すでに今期末での解約が予約されています。')
            return redirect('accounts:mypage')

        # 今期末で解約に更新
        sub = stripe.Subscription.modify(sub_id, cancel_at_period_end=True)

        # ローカルに終了日を反映
        period_end_ts = getattr(sub, 'current_period_end', None)
        if period_end_ts:
            sub_model.end_date = datetime.fromtimestamp(period_end_ts, tz=timezone.utc).date()
        # 今期末までは利用可とする（is_activeは維持）
        sub_model.save()

        messages.success(request, '解約を受け付けました。現在の支払期間の終了日までご利用いただけます。')
        return redirect('accounts:mypage')

    except stripe.error.StripeError as e:
        messages.error(request, f"解約に失敗しました: {getattr(e, 'user_message', None) or str(e)}")
        return redirect('accounts:mypage')
    except Exception as e:
        messages.error(request, 'サーバーエラーが発生しました。')
        return redirect('accounts:mypage')


# ログアウト
def logout_view(request):
    # Django標準のlogout()関数でセッションを削除
    logout(request)
    # ログアウト完了メッセージを設定
    messages.success(request, 'ログアウトしました。', extra_tags='auth')
    # 店舗一覧ページにリダイレクト
    return redirect('shops:shop_list')


# StripeのAPIキー設定
stripe.api_key = settings.STRIPE_API_SECRET_KEY

# 決済成功ページ
class PaySuccessView(TemplateView):
    template_name = 'accounts/pay_success.html'

    def get_context_data(self, **kwargs):
        
        # 親からのコンテキストを取得
        context = super().get_context_data(**kwargs)
        
        # セッションIDの取得
        session_id = self.request.GET.get('session_id')

        # パラメーターがなければ何もしない
        if not session_id:
            return context
        
        try:
            # stripeのチェックアウトセッションを取得
            session = stripe.checkout.Session.retrieve(session_id)

            # 支払いが成功してる場合はDB更新
            if session.payment_status == 'paid' and self.request.user.is_authenticated:
            
                # モデルを取得
                subscription, created = Subscription.objects.get_or_create(user=self.request.user)

                # セッション情報を保存
                subscription.stripe_id = session.id
                # ここを追加: 顧客ID/サブスクリプションIDを保存
                try:
                    subscription.stripe_customer_id = getattr(session, 'customer', None)
                    subscription.stripe_subscription_id = getattr(session, 'subscription', None)
                except Exception:
                    pass
                subscription.is_active = True
                subscription.save()

        # 取得失敗などのstripe側のエラー
        except stripe.error.StripeError as e:
            context['error'] = f'stripeエラー: {str(e)}'

        return context


# 決済キャンセルページ
class PayCancelView(TemplateView):
    template_name = 'accounts/pay_cancel.html'

@method_decorator(login_required, name='dispatch')
class StripeBillingPortalView(View):
    """Stripeカスタマーポータルへ遷移するためのビュー"""
    def get(self, request, *args, **kwargs):
        try:
            # 契約履歴の有無
            try:
                subscription = request.user.subscription
            except Subscription.DoesNotExist:
                return redirect(str(reverse_lazy('accounts:mypage')) + '?err=no_subscription')

            # 顧客IDが未保存のときは、Checkoutセッションから補完を試みる
            if not getattr(subscription, 'stripe_customer_id', None) and getattr(subscription, 'stripe_id', None):
                try:
                    sid = str(subscription.stripe_id)
                    if sid.startswith('cs_'):
                        cs = stripe.checkout.Session.retrieve(sid)
                        cust = getattr(cs, 'customer', None)
                        subid = getattr(cs, 'subscription', None)
                        updated = False
                        if cust and not subscription.stripe_customer_id:
                            subscription.stripe_customer_id = cust
                            updated = True
                        if subid and not getattr(subscription, 'stripe_subscription_id', None):
                            subscription.stripe_subscription_id = subid
                            updated = True
                        if updated:
                            subscription.save()
                except Exception:
                    pass

            # 追加フォールバック: subscription_id から顧客IDを補完
            if not getattr(subscription, 'stripe_customer_id', None) and getattr(subscription, 'stripe_subscription_id', None):
                try:
                    sub = stripe.Subscription.retrieve(subscription.stripe_subscription_id)
                    cust = getattr(sub, 'customer', None)
                    if cust:
                        subscription.stripe_customer_id = cust
                        subscription.save()
                except Exception:
                    pass

            # なお顧客IDが無ければ編集画面を開けない
            if not getattr(subscription, 'stripe_customer_id', None):
                return redirect(str(reverse_lazy('accounts:mypage')) + '?err=no_customer')

            # 顧客IDの妥当性チェック（削除済み/環境不一致の検知）
            try:
                _ = stripe.Customer.retrieve(subscription.stripe_customer_id)
            except stripe.error.InvalidRequestError as e:
                # 既存IDが無効。subscription_idから再補完を試みる
                try:
                    if getattr(subscription, 'stripe_subscription_id', None):
                        sub = stripe.Subscription.retrieve(subscription.stripe_subscription_id)
                        cust2 = getattr(sub, 'customer', None)
                        if cust2:
                            subscription.stripe_customer_id = cust2
                            subscription.save()
                except Exception:
                    pass
                # まだ無ければエラーとして返す（理由付き）
                if not getattr(subscription, 'stripe_customer_id', None):
                    reason = urllib.parse.quote(getattr(e, 'user_message', None) or str(e))
                    return redirect(str(reverse_lazy('accounts:mypage')) + f'?err=no_customer&reason={reason}')

            # カスタマーポータルのセッションを作成
            # return_url は絶対URLが必要。開発環境では 127.0.0.1/0.0.0.0/::1 を localhost に置換
            return_path = str(reverse_lazy('accounts:mypage'))
            return_url = request.build_absolute_uri(return_path)
            if settings.DEBUG:
                for host in ['127.0.0.1', '0.0.0.0', '::1']:
                    if host in return_url:
                        return_url = return_url.replace(host, 'localhost')

            try:
                kwargs = {
                    'customer': subscription.stripe_customer_id,
                    'return_url': return_url,
                }
                config_id = getattr(settings, 'STRIPE_BILLING_PORTAL_CONFIGURATION_ID', None)
                if config_id:
                    kwargs['configuration'] = config_id
                portal = stripe.billing_portal.Session.create(**kwargs)
            except stripe.error.StripeError as e:
                reason = getattr(e, 'user_message', None) or str(e)
                qs = '?err=portal_failed&reason=' + urllib.parse.quote(reason)
                return redirect(str(reverse_lazy('accounts:mypage')) + qs)

            return redirect(portal.url)
        except Exception as e:
            reason = urllib.parse.quote(str(e))
            return redirect(str(reverse_lazy('accounts:mypage')) + f'?err=portal_failed&reason={reason}')

@method_decorator(login_required, name='dispatch')
class PayWithStripeView(View):
    
    def _create_checkout_session(self, request):
        """
        セッション作成と、作成した session_id のDB保存を行う共通処理
        """
        # 成否に関わらず使うURL（型を明示的にstrへ）
        success_url = f"{settings.MY_URL}{str(reverse_lazy('accounts:pay_success'))}?session_id={{CHECKOUT_SESSION_ID}}"
        cancel_url = f"{settings.MY_URL}{str(reverse_lazy('accounts:pay_cancel'))}"

        # Price ID（後方互換: STRIPE_PRICE_ID_JPY_300 or STRIPE_PRICE_ID）
        price_id = getattr(settings, 'STRIPE_PRICE_ID_JPY_300', None) or getattr(settings, 'STRIPE_PRICE_ID', None)

        checkout_session = None
        try:
            if price_id:
                # まずは既存のPriceで作成を試す
                checkout_session = stripe.checkout.Session.create(
                    mode='subscription',
                    line_items=[{'price': price_id, 'quantity': 1}],
                    success_url=success_url,
                    cancel_url=cancel_url,
                )
        except stripe.error.StripeError:
            # Price が無効/存在しない等のケースはフォールバックへ
            checkout_session = None

        if checkout_session is None:
            # フォールバック: その場でJPY 300/月を組み立て
            checkout_session = stripe.checkout.Session.create(
                mode='subscription',
                line_items=[{
                    'price_data': {
                        'currency': 'jpy',
                        'recurring': {'interval': 'month'},
                        'product_data': {'name': 'NagoyaMeshi プレミアム（¥300/月）'},
                        'unit_amount': 300,
                    },
                    'quantity': 1,
                }],
                success_url=success_url,
                cancel_url=cancel_url,
            )

        # 直近のセッションIDをDBへ保存（決済完了前なのでis_activeはFalseのまま）
        subscription, _ = Subscription.objects.get_or_create(user=request.user)
        subscription.stripe_id = checkout_session.id
        subscription.is_active = False
        subscription.save()

        return checkout_session

    def get(self, request, *args, **kwargs):
        try:
            session = self._create_checkout_session(request)
            return redirect(session.url)
        except Exception as e:
            # このメッセージはマイページでのみ表示される（login_requiredで未ログインはここに来ない）
            messages.error(request, f'決済の開始に失敗しました: {e}')
            return redirect('accounts:mypage')

    def post(self, request, *args, **kwargs):
        try:
            session = self._create_checkout_session(request)
            return JsonResponse({'success': True, 'id': session.id, 'checkout_url': getattr(session, 'url', None)})
        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)}, status=500)