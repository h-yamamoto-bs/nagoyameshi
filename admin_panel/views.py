from django.shortcuts import render, redirect, get_object_or_404
from django.views.generic import TemplateView, ListView, CreateView, UpdateView, DeleteView, DetailView
from django.contrib.auth.views import LoginView, LogoutView
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib import messages
from django.urls import reverse_lazy, reverse
from django.db.models import Q, Count, Sum, Avg
from django.db import models
from django.http import HttpResponse, JsonResponse
from django.views.decorators.http import require_POST
from django.core.cache import cache
import csv
from datetime import datetime, timedelta
from django.utils import timezone

from accounts.models import User
from shops.models import Shop, Category, ShopCategory
from .models import CompanyInfo


class AdminRequiredMixin(UserPassesTestMixin):
    """管理者権限が必要なビューのベースクラス"""
    def test_func(self):
        user = self.request.user
        # デバッグ用ログ（本番環境では削除予定）
        if hasattr(user, 'email'):
            print(f"AdminRequiredMixin check - User: {user.email}, authenticated: {user.is_authenticated}, manager_flag: {getattr(user, 'manager_flag', None)}")
        
        return (user.is_authenticated and 
                hasattr(user, 'manager_flag') and 
                user.manager_flag)
    
    def handle_no_permission(self):
        # セッションをクリアしてリダイレクトループを防ぐ
        if hasattr(self.request, 'session'):
            self.request.session.flush()
        
        if not self.request.user.is_authenticated:
            # 未認証ユーザーは管理者ログイン画面へ
            return redirect('admin_panel:login')
        else:
            # 認証済みだが管理者権限なしの場合、メッセージを表示してログアウト
            messages.error(self.request, '管理者権限が必要です。一般ユーザーアカウントではアクセスできません。')
            from django.contrib.auth import logout
            logout(self.request)
            return redirect('admin_panel:login')


class AdminLoginView(LoginView):
    """管理者ログイン"""
    template_name = 'admin_panel/login.html'
    redirect_authenticated_user = False  # リダイレクトループを防ぐため無効化
    
    def dispatch(self, request, *args, **kwargs):
        # セッションクリア処理
        if request.GET.get('clear_session'):
            request.session.flush()
            from django.contrib.auth import logout
            logout(request)
            messages.success(request, 'セッションをクリアしました。再度ログインしてください。')
            return redirect('admin_panel:login')
        
        # デバッグ用ログ
        user = request.user
        if hasattr(user, 'email'):
            print(f"AdminLoginView dispatch - User: {user.email}, authenticated: {user.is_authenticated}, manager_flag: {getattr(user, 'manager_flag', None)}")
        
        # 認証済みかつ管理者権限があるユーザーは dashboard にリダイレクト
        if (user.is_authenticated and 
            hasattr(user, 'manager_flag') and 
            user.manager_flag):
            print(f"Redirecting authenticated admin user to dashboard")
            return redirect('admin_panel:dashboard')
        
        # 認証済みだが管理者権限がないユーザーはログアウトしてからログイン画面表示
        elif user.is_authenticated:
            print(f"Logging out non-admin user: {user.email}")
            from django.contrib.auth import logout
            logout(request)
            messages.info(request, 'ログアウトしました。管理者アカウントでログインしてください。')
        
        return super().dispatch(request, *args, **kwargs)
    
    def get_success_url(self):
        return reverse_lazy('admin_panel:dashboard')
    
    def form_valid(self, form):
        user = form.get_user()
        if not hasattr(user, 'manager_flag') or not user.manager_flag:
            messages.error(self.request, '管理者権限がありません。')
            return self.form_invalid(form)
        return super().form_valid(form)


class AdminLogoutView(LogoutView):
    """管理者ログアウト"""
    next_page = 'admin_panel:login'


class AdminDashboardView(AdminRequiredMixin, TemplateView):
    """管理者ダッシュボード"""
    template_name = 'admin_panel/dashboard.html'
    
    def dispatch(self, request, *args, **kwargs):
        # 二重チェック：認証状態を再確認
        user = request.user
        if not (user.is_authenticated and hasattr(user, 'manager_flag') and user.manager_flag):
            print(f"Dashboard access denied - User: {getattr(user, 'email', 'Anonymous')}, authenticated: {user.is_authenticated}, manager_flag: {getattr(user, 'manager_flag', None)}")
            messages.error(request, '管理者ダッシュボードへのアクセスが拒否されました。')
            return redirect('admin_panel:login')
        
        return super().dispatch(request, *args, **kwargs)
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # キャッシュキー
        cache_key = 'admin_dashboard_stats'
        stats = cache.get(cache_key)
        
        if stats is None:
            # 統計情報を1クエリで効率的に取得
            from django.db import connection
            with connection.cursor() as cursor:
                cursor.execute("""
                    SELECT 
                        (SELECT COUNT(*) FROM shops) as shop_count,
                        (SELECT COUNT(*) FROM auth_user WHERE manager_flag = 0) as user_count,
                        (SELECT COUNT(*) FROM categories) as category_count
                """)
                row = cursor.fetchone()
                stats = {
                    'shop_count': row[0],
                    'user_count': row[1],
                    'category_count': row[2]
                }
            
            # 5分間キャッシュ
            cache.set(cache_key, stats, 300)
        
        context.update(stats)
        return context


class CompanyInfoView(AdminRequiredMixin, TemplateView):
    """会社情報管理"""
    template_name = 'admin_panel/company_info.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        try:
            context['company'] = CompanyInfo.objects.first()
        except CompanyInfo.DoesNotExist:
            context['company'] = None
        return context
    
    def post(self, request):
        data = request.POST
        company, created = CompanyInfo.objects.get_or_create(pk=1)
        
        company.name = data.get('name', '')
        company.postal_code = data.get('postal_code', '')
        company.address = data.get('address', '')
        company.phone = data.get('phone', '')
        company.email = data.get('email', '')
        company.description = data.get('description', '')
        company.save()
        
        messages.success(request, '会社情報を更新しました。')
        return redirect('admin_panel:company_info')


class ShopListView(AdminRequiredMixin, ListView):
    """店舗一覧"""
    model = Shop
    template_name = 'admin_panel/shop_list.html'
    context_object_name = 'shops'
    paginate_by = 20
    
    def get_queryset(self):
        # N+1問題を避けるため、関連データを事前に取得
        queryset = Shop.objects.select_related('user').prefetch_related(
            'categories__category'
        )
        search = self.request.GET.get('search')
        if search:
            queryset = queryset.filter(name__icontains=search)
        return queryset.order_by('-id')


class ShopCreateView(AdminRequiredMixin, CreateView):
    """店舗作成"""
    model = Shop
    template_name = 'admin_panel/shop_form.html'
    fields = ['name', 'address', 'seat_count', 'phone_number', 'user']
    success_url = reverse_lazy('admin_panel:shop_list')
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['title'] = '店舗登録'
        context['categories'] = Category.objects.all()
        context['selected_categories'] = []  # 新規作成時は空
        return context
    
    def form_valid(self, form):
        # 店舗の基本情報を保存
        response = super().form_valid(form)
        
        # カテゴリの処理
        shop = form.instance
        category_ids = self.request.POST.getlist('categories')  # チェックボックスから選択されたカテゴリIDのリスト
        
        # カテゴリ関連を作成
        for category_id in category_ids:
            try:
                category = Category.objects.get(id=category_id)
                ShopCategory.objects.create(shop=shop, category=category)
            except Category.DoesNotExist:
                continue
        
        messages.success(self.request, '店舗とカテゴリを登録しました。')
        return response


class ShopEditView(AdminRequiredMixin, UpdateView):
    """店舗編集"""
    model = Shop
    template_name = 'admin_panel/shop_form.html'
    fields = ['name', 'address', 'seat_count', 'phone_number', 'user']
    success_url = reverse_lazy('admin_panel:shop_list')
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['title'] = '店舗編集'
        context['categories'] = Category.objects.all()
        
        # 現在選択されているカテゴリを取得
        shop = self.get_object()
        selected_categories = [sc.category.id for sc in shop.categories.select_related('category')]
        context['selected_categories'] = selected_categories
        
        return context
    
    def form_valid(self, form):
        # 店舗の基本情報を保存
        response = super().form_valid(form)
        
        # カテゴリの処理
        shop = form.instance
        category_ids = self.request.POST.getlist('categories')  # チェックボックスから選択されたカテゴリIDのリスト
        
        # 既存のカテゴリ関連を削除
        shop.categories.all().delete()
        
        # 新しいカテゴリ関連を作成
        for category_id in category_ids:
            try:
                category = Category.objects.get(id=category_id)
                ShopCategory.objects.create(shop=shop, category=category)
            except Category.DoesNotExist:
                continue
        
        messages.success(self.request, '店舗情報とカテゴリを更新しました。')
        return response


class ShopDetailView(AdminRequiredMixin, DetailView):
    """店舗詳細"""
    model = Shop
    template_name = 'admin_panel/shop_detail.html'
    context_object_name = 'shop'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        shop = self.get_object()
        
        # 店舗の統計情報
        context['total_reviews'] = shop.reviews.count()
        context['avg_rating'] = shop.reviews.aggregate(avg_rating=Avg('rating'))['avg_rating'] or 0
        context['total_reservations'] = shop.histories.count()
        context['total_favorites'] = shop.favorites.count()
        
        # 最近のレビュー
        context['recent_reviews'] = shop.reviews.select_related('user').order_by('-created_at')[:5]
        
        # 最近の予約
        context['recent_reservations'] = shop.histories.select_related('user').order_by('-created_at')[:10]
        
        return context


class ShopDeleteView(AdminRequiredMixin, DeleteView):
    """店舗削除"""
    model = Shop
    template_name = 'admin_panel/shop_confirm_delete.html'
    success_url = reverse_lazy('admin_panel:shop_list')
    
    def delete(self, request, *args, **kwargs):
        messages.success(request, '店舗を削除しました。')
        return super().delete(request, *args, **kwargs)


@login_required
@user_passes_test(lambda u: u.manager_flag)
def shop_csv_export(request):
    """店舗CSV出力"""
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = 'attachment; filename="shops.csv"'
    response.write('\ufeff')  # BOM for Excel
    
    writer = csv.writer(response)
    writer.writerow(['ID', '店舗名', '住所', '席数', '電話番号', '管理者メール'])
    
    for shop in Shop.objects.select_related('user'):
        writer.writerow([
            shop.id,
            shop.name,
            shop.address,
            shop.seat_count,
            shop.phone_number or '',
            shop.user.email
        ])
    
    return response


@login_required  
@user_passes_test(lambda u: u.manager_flag)
def shop_csv_import(request):
    """店舗CSV入力"""
    if request.method == 'POST':
        csv_file = request.FILES.get('csv_file')
        if not csv_file:
            messages.error(request, 'CSVファイルを選択してください。')
            return redirect('admin_panel:shop_list')
        
        try:
            decoded_file = csv_file.read().decode('utf-8')
            reader = csv.reader(decoded_file.splitlines())
            next(reader)  # ヘッダースキップ
            
            created_count = 0
            for row in reader:
                if len(row) >= 5:
                    try:
                        user = User.objects.get(email=row[5])
                        shop, created = Shop.objects.get_or_create(
                            name=row[1],
                            defaults={
                                'address': row[2],
                                'seat_count': int(row[3]),
                                'phone_number': row[4],
                                'user': user
                            }
                        )
                        if created:
                            created_count += 1
                    except (User.DoesNotExist, ValueError):
                        continue
            
            messages.success(request, f'{created_count}件の店舗を登録しました。')
        except Exception as e:
            messages.error(request, f'CSVの読み込みでエラーが発生しました: {str(e)}')
    
    return redirect('admin_panel:shop_list')


class UserListView(AdminRequiredMixin, ListView):
    """会員一覧"""
    model = User
    template_name = 'admin_panel/user_list.html'
    context_object_name = 'users'
    paginate_by = 20
    
    def get_queryset(self):
        queryset = User.objects.all()
        
        # 検索フィルター（emailのみ）
        search = self.request.GET.get('search')
        if search:
            # メールアドレスで検索
            queryset = queryset.filter(email__icontains=search)
        
        return queryset.order_by('-id')
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # 統計情報を効率的に計算（1クエリで全て取得）
        user_stats = User.objects.aggregate(
            total_users=Count('id', filter=models.Q(manager_flag=False)),
            managers_count=Count('id', filter=models.Q(manager_flag=True))
        )
        
        context.update(user_stats)
        
        # サブスクリプションテーブルがある場合の有料会員数
        try:
            from accounts.models import Subscription
            context['subscribed_users'] = User.objects.filter(
                manager_flag=False, 
                subscription__isnull=False,
                subscription__is_active=True
            ).distinct().count()
        except:
            context['subscribed_users'] = 0
        
        # 新規ユーザー数（今月） - date_joinedがないので0に設定
        context['new_users_this_month'] = 0
        
        # 現在の検索パラメータを保持
        context['current_search'] = self.request.GET.get('search', '')
        
        return context


class UserCreateView(AdminRequiredMixin, CreateView):
    """会員作成"""
    model = User
    template_name = 'admin_panel/user_form.html'
    fields = ['email', 'job', 'birth_year', 'manager_flag']
    success_url = reverse_lazy('admin_panel:user_list')
    
    def form_valid(self, form):
        # パスワードの設定
        password = self.request.POST.get('password')
        if password:
            form.instance.set_password(password)
        else:
            # デフォルトパスワードを設定
            form.instance.set_password('password123')
        return super().form_valid(form)


class UserEditView(AdminRequiredMixin, UpdateView):
    """会員編集"""
    model = User
    template_name = 'admin_panel/user_form.html'
    fields = ['email', 'job', 'birth_year', 'is_active', 'manager_flag']
    success_url = reverse_lazy('admin_panel:user_list')
    
    def get_form(self, form_class=None):
        form = super().get_form(form_class)
        # Bootstrapクラスを追加
        form.fields['email'].widget.attrs.update({'class': 'form-control', 'required': True})
        form.fields['job'].widget.attrs.update({'class': 'form-control'})
        form.fields['birth_year'].widget.attrs.update({'class': 'form-control', 'min': 1900, 'max': 2024})
        form.fields['is_active'].widget.attrs.update({'class': 'form-check-input'})
        form.fields['manager_flag'].widget.attrs.update({'class': 'form-check-input'})
        return form
    
    def form_valid(self, form):
        messages.success(self.request, 'ユーザー情報を更新しました。')
        return super().form_valid(form)


class UserDetailView(AdminRequiredMixin, DetailView):
    """会員詳細"""
    model = User
    template_name = 'admin_panel/user_detail.html'
    context_object_name = 'user'
    
    def get_queryset(self):
        return User.objects.filter(manager_flag=False)


class UserDeleteView(AdminRequiredMixin, DeleteView):
    """会員削除"""
    model = User
    template_name = 'admin_panel/user_confirm_delete.html'
    success_url = reverse_lazy('admin_panel:user_list')
    
    def delete(self, request, *args, **kwargs):
        messages.success(request, 'ユーザーを削除しました。')
        return super().delete(request, *args, **kwargs)
    
    def get_queryset(self):
        # 管理者は削除不可
        return User.objects.filter(manager_flag=False)


@login_required
@user_passes_test(lambda u: u.manager_flag)
def user_csv_export(request):
    """会員CSV出力"""
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = 'attachment; filename="users.csv"'
    response.write('\ufeff')  # BOM for Excel
    
    writer = csv.writer(response)
    writer.writerow(['ID', 'メールアドレス', '職業', '生年', '登録日', '有効'])
    
    for user in User.objects.filter(manager_flag=False):
        writer.writerow([
            user.id,
            user.email,
            user.job or '',
            user.birth_year or '',
            user.date_joined.strftime('%Y-%m-%d') if hasattr(user, 'date_joined') else '',
            '有効' if user.is_active else '無効'
        ])
    
    return response


class CategoryListView(AdminRequiredMixin, ListView):
    """カテゴリ一覧"""
    model = Category
    template_name = 'admin_panel/category_list.html'
    context_object_name = 'categories'
    paginate_by = 20
    
    def get_queryset(self):
        from shops.models import ShopCategory
        queryset = Category.objects.annotate(
            shop_count=Count('shop_categories')
        )
        search = self.request.GET.get('search')
        if search:
            queryset = queryset.filter(name__icontains=search)
        
        # ソート機能
        sort = self.request.GET.get('sort', 'name')
        if sort == 'created':
            queryset = queryset.order_by('id')
        elif sort == 'shop_count':
            queryset = queryset.order_by('-shop_count', 'name')
        else:  # name
            queryset = queryset.order_by('name')
            
        return queryset
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # 統計情報を効率的に計算（1クエリで全て取得）
        stats = Category.objects.annotate(
            shop_count=Count('shop_categories')
        ).aggregate(
            total=Count('id'),
            used=Count('id', filter=models.Q(shop_count__gt=0)),
            unused=Count('id', filter=models.Q(shop_count=0)),
            avg_shops=Avg('shop_count')
        )
        
        context.update({
            'used_categories_count': stats['used'],
            'unused_categories_count': stats['unused'],
            'avg_shops_per_category': stats['avg_shops'] or 0,
        })
        
        return context


class CategoryShopsView(AdminRequiredMixin, ListView):
    """カテゴリに属する店舗一覧"""
    model = Shop
    template_name = 'admin_panel/category_shops.html'
    context_object_name = 'shops'
    paginate_by = 20
    
    def get_queryset(self):
        from shops.models import ShopCategory
        category_id = self.kwargs['category_id']
        
        # カテゴリに属する店舗を取得
        shop_categories = ShopCategory.objects.filter(category_id=category_id)
        shop_ids = shop_categories.values_list('shop_id', flat=True)
        
        queryset = Shop.objects.filter(id__in=shop_ids).select_related('user').prefetch_related('images')
        
        # 検索機能
        search = self.request.GET.get('search')
        if search:
            queryset = queryset.filter(name__icontains=search)
        
        return queryset.order_by('name')
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        category_id = self.kwargs['category_id']
        
        try:
            category = Category.objects.get(id=category_id)
            context['category'] = category
        except Category.DoesNotExist:
            context['category'] = None
        
        return context


class CategoryCreateView(AdminRequiredMixin, CreateView):
    """カテゴリ作成"""
    model = Category
    template_name = 'admin_panel/category_form.html'
    fields = ['name']
    success_url = reverse_lazy('admin_panel:category_list')
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['title'] = 'カテゴリ登録'
        return context
    
    def form_valid(self, form):
        messages.success(self.request, 'カテゴリを登録しました。')
        return super().form_valid(form)


class CategoryEditView(AdminRequiredMixin, UpdateView):
    """カテゴリ編集"""
    model = Category
    template_name = 'admin_panel/category_form.html'
    fields = ['name']
    success_url = reverse_lazy('admin_panel:category_list')
    
    def get_form(self, form_class=None):
        form = super().get_form(form_class)
        # Bootstrapクラスを追加
        form.fields['name'].widget.attrs.update({'class': 'form-control', 'required': True})
        return form
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['title'] = 'カテゴリ編集'
        return context
    
    def form_valid(self, form):
        messages.success(self.request, 'カテゴリを更新しました。')
        return super().form_valid(form)


class CategoryDeleteView(AdminRequiredMixin, DeleteView):
    """カテゴリ削除"""
    model = Category
    template_name = 'admin_panel/category_confirm_delete.html'
    success_url = reverse_lazy('admin_panel:category_list')
    
    def delete(self, request, *args, **kwargs):
        messages.success(request, 'カテゴリを削除しました。')
        return super().delete(request, *args, **kwargs)
