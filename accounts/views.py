from django.shortcuts import render, redirect
from .models import User
from django.views.generic import ListView, TemplateView
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.forms import AuthenticationForm
from django.contrib import messages
from django.urls import reverse_lazy
from django.views.generic import CreateView
from django.contrib.auth.forms import UserCreationForm

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
            messages.error(request, 'メールアドレスまたはパスワードが間違っています。')
        
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

# ログアウト
def logout_view(request):
    # Django標準のlogout()関数でセッションを削除
    logout(request)
    # ログアウト完了メッセージを設定
    messages.success(request, 'ログアウトしました。')
    # 店舗一覧ページにリダイレクト
    return redirect('shops:shop_list')