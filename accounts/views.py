from django.shortcuts import render, redirect
from .models import User, Subscription
from shops.models import Favorite, Review
from django.views.generic import ListView, TemplateView
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

# ユーザー一覧
class AccountListView(ListView):
    model = User
    template_name = 'accounts/account_list.html'
    context_object_name = 'users'

# ログイン
class LoginView(TemplateView):
    template_name = 'accounts/login.html'

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
                    messages.success(request, 'ログインしました。')
                    # リダイレクト
                    next_url = request.GET.get('next', 'shops:shop_list')
                    return redirect('shops:shop_list')
                else:   # 無効の場合
                    messages.error(request, 'アカウントが無効です。')
            else:  # 認証失敗
                messages.error(request, 'メールアドレスまたはパスワードが間違っています。')
        
        except User.DoesNotExist:
            messages.error(request, 'このメールアドレスは登録されていません。新規登録をお試しください。')
        
        # ログイン失敗時の処理
        return render(request, self.template_name, {
            'form': AuthenticationForm(),
            'email': email
        })

# 新規登録
class RegisterView(TemplateView):
    template_name = 'accounts/register.html'

    def post(self, request, *args, **kwargs):

        # フォームからデータ取得
        email = request.POST.get('email')
        password = request.POST.get('password')
        password_confirm = request.POST.get('password_confirm')

        # 必須項目のチェック
        if not email or not password or not password_confirm:
            messages.error(request, 'すべてのフィールドを入力してください。')
            return render(request, self.template_name, {'email': email, 'password': password, 'password_confirm': password_confirm})

        # パスワードの一致確認
        if password != password_confirm:
            messages.error(request, 'パスワードが一致しません。')
            return render(request, self.template_name, {'email': email, 'password': password, 'password_confirm': password_confirm})

        # メールアドレス重複チェック
        if User.objects.filter(email=email).exists():
            messages.error(request, 'このメールアドレスは既に登録されています。')
            return render(request, self.template_name, {'email': email})
        
        # ユーザー作成
        try:
            user = User.objects.create_user(
                email=email,
                password=password
            )

            # 成功メッセージ
            messages.success(request, 'アカウントが作成されました。ログインしてください。')

            # ログインページにリダイレクト
            return redirect('accounts:login')
        
        except Exception as e:
            messages.error(request, f'アカウントの作成に失敗しました: {str(e)}')
            return render(request, self.template_name, {'email': email})

class MyPageView(LoginRequiredMixin, TemplateView):
    template_name = 'accounts/mypage.html'
    login_url = reverse_lazy('accounts:login')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.request.user
        
        # サブスクリプション情報の取得
        try:
            subscription = user.subscription
        except Subscription.DoesNotExist:
            subscription = None
        
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
    """サブスクリプション情報更新API"""
    try:
        user = request.user
        
        # フォームデータの取得
        is_active = request.POST.get('is_active') == 'true'
        
        # サブスクリプション情報の取得または作成
        subscription, created = Subscription.objects.get_or_create(
            user=user,
            defaults={'is_active': is_active}
        )
        
        if not created:
            # 既存のサブスクリプション情報を更新
            subscription.is_active = is_active
            subscription.save()
        
        return JsonResponse({
            'success': True,
            'message': 'サブスクリプション情報が更新されました。'
        })
    
    except Exception as e:
        return JsonResponse({
            'success': False,
            'message': 'サーバーエラーが発生しました。'
        }, status=500)


# ログアウト
def logout_view(request):
    # Django標準のlogout()関数でセッションを削除
    logout(request)
    # ログアウト完了メッセージを設定
    messages.success(request, 'ログアウトしました。')
    # 店舗一覧ページにリダイレクト
    return redirect('shops:shop_list')