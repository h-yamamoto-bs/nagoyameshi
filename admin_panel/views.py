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
import csv
from datetime import datetime, timedelta
from django.utils import timezone

from accounts.models import User
from shops.models import Shop, Review, Category, History
from .models import CompanyInfo


class AdminRequiredMixin(UserPassesTestMixin):
    """管理者権限が必要なビューのベースクラス"""
    def test_func(self):
        return self.request.user.is_authenticated and self.request.user.manager_flag
    
    def handle_no_permission(self):
        return redirect('admin_panel:login')


class AdminLoginView(LoginView):
    """管理者ログイン"""
    template_name = 'admin_panel/login.html'
    redirect_authenticated_user = True
    
    def get_success_url(self):
        return reverse_lazy('admin_panel:dashboard')
    
    def form_valid(self, form):
        user = form.get_user()
        if not user.manager_flag:
            messages.error(self.request, '管理者権限がありません。')
            return self.form_invalid(form)
        return super().form_valid(form)


class AdminLogoutView(LogoutView):
    """管理者ログアウト"""
    next_page = 'admin_panel:login'


class AdminDashboardView(AdminRequiredMixin, TemplateView):
    """管理者ダッシュボード"""
    template_name = 'admin_panel/dashboard.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        # 統計情報を取得
        context['shop_count'] = Shop.objects.count()
        context['user_count'] = User.objects.filter(manager_flag=False).count()
        context['review_count'] = Review.objects.count()
        context['category_count'] = Category.objects.count()
        
        # 最近の売上（過去30日）
        thirty_days_ago = timezone.now() - timedelta(days=30)
        recent_sales = History.objects.filter(
            created_at__gte=thirty_days_ago
        ).aggregate(total=Sum('number_of_people'))
        context['recent_reservations'] = recent_sales['total'] or 0
        
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
        queryset = Shop.objects.select_related('user').prefetch_related('categories__category')
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
        return context
    
    def form_valid(self, form):
        messages.success(self.request, '店舗を登録しました。')
        return super().form_valid(form)


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
        return context
    
    def form_valid(self, form):
        messages.success(self.request, '店舗情報を更新しました。')
        return super().form_valid(form)


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
        queryset = User.objects.filter(manager_flag=False)
        search = self.request.GET.get('search')
        if search:
            queryset = queryset.filter(email__icontains=search)
        return queryset.order_by('-id')
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['total_users'] = User.objects.filter(manager_flag=False).count()
        
        # サブスクリプションテーブルがある場合の有料会員数
        try:
            from accounts.models import Subscription
            context['subscribed_users'] = User.objects.filter(
                manager_flag=False, 
                subscription__isnull=False
            ).distinct().count()
        except:
            context['subscribed_users'] = 0
        
        # 新規ユーザー数（今月） - date_joinedがないので0に設定
        context['new_users_this_month'] = 0
        
        context['managers_count'] = User.objects.filter(manager_flag=True).count()
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
        
        # 統計情報を追加
        categories = Category.objects.annotate(shop_count=Count('shop_categories'))
        total_categories = categories.count()
        used_categories = categories.filter(shop_count__gt=0).count()
        unused_categories = categories.filter(shop_count=0).count()
        
        # 平均店舗数を計算
        avg_shops = categories.aggregate(avg=Avg('shop_count'))['avg'] or 0
        
        context.update({
            'used_categories_count': used_categories,
            'unused_categories_count': unused_categories,
            'avg_shops_per_category': avg_shops,
        })
        
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


class ReviewListView(AdminRequiredMixin, ListView):
    """レビュー一覧"""
    model = Review
    template_name = 'admin_panel/review_list.html'
    context_object_name = 'reviews'
    paginate_by = 20  # デフォルトは20件
    
    def get_queryset(self):
        queryset = Review.objects.select_related('user', 'shop')
        
        # 検索
        search = self.request.GET.get('search')
        if search:
            queryset = queryset.filter(
                Q(shop__name__icontains=search) |
                Q(user__email__icontains=search)
            )
        
        # ステータスフィルター
        status = self.request.GET.get('status')
        if status == 'visible':
            queryset = queryset.filter(is_visible=True)
        elif status == 'hidden':
            queryset = queryset.filter(is_visible=False)
        
        # 評価フィルター
        rating = self.request.GET.get('rating')
        if rating:
            queryset = queryset.filter(rating=rating)
        
        # ソート
        sort = self.request.GET.get('sort', '-created_at')
        queryset = queryset.order_by(sort)
        
        return queryset
    
    def get_paginate_by(self, queryset):
        """ページネーションの件数を動的に変更"""
        show_all = self.request.GET.get('show_all')
        if show_all == 'true':
            return None  # すべて表示
        return self.paginate_by
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['total_reviews'] = Review.objects.count()
        context['approved_reviews'] = Review.objects.filter(is_visible=True).count()
        context['pending_reviews'] = Review.objects.filter(is_visible=False).count()
        
        # 平均評価を計算
        from django.db.models import Avg
        avg_rating = Review.objects.aggregate(Avg('rating'))['rating__avg']
        context['avg_rating'] = avg_rating if avg_rating else 0
        
        # デバッグ情報
        context['show_all'] = self.request.GET.get('show_all') == 'true'
        context['current_page_size'] = len(context.get('reviews', []))
        
        # Ajax読み込み用の情報
        context['is_ajax'] = self.request.headers.get('X-Requested-With') == 'XMLHttpRequest'
            
        return context
    
    def render_to_response(self, context, **response_kwargs):
        # Ajax リクエストの場合は部分テンプレートを返す
        if self.request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            from django.template.loader import render_to_string
            from django.http import JsonResponse
            
            # レビューカードのHTMLを生成
            reviews_html = render_to_string('admin_panel/review_cards.html', {
                'reviews': context['reviews'],
                'request': self.request
            })
            
            return JsonResponse({
                'success': True,
                'html': reviews_html,
                'has_next': context.get('page_obj').has_next() if context.get('page_obj') else False,
                'next_page': context.get('page_obj').next_page_number() if context.get('page_obj') and context.get('page_obj').has_next() else None,
                'total_count': context['total_reviews'],
                'current_count': context['current_page_size']
            })
        
        return super().render_to_response(context, **response_kwargs)
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['total_reviews'] = Review.objects.count()
        context['approved_reviews'] = Review.objects.filter(is_visible=True).count()
        context['pending_reviews'] = Review.objects.filter(is_visible=False).count()
        
        # 平均評価を計算
        from django.db.models import Avg
        avg_rating = Review.objects.aggregate(Avg('rating'))['rating__avg']
        context['avg_rating'] = avg_rating if avg_rating else 0
        
        # デバッグ情報
        context['show_all'] = self.request.GET.get('show_all') == 'true'
        context['current_page_size'] = len(context.get('reviews', []))
        
        return context


@login_required
@user_passes_test(lambda u: u.manager_flag)
@require_POST
def toggle_review_visibility(request, pk):
    """レビュー表示/非表示切り替え"""
    import json
    
    try:
        review = get_object_or_404(Review, pk=pk)
        
        # リクエストボディを取得
        if request.body:
            data = json.loads(request.body)
            is_visible = data.get('is_visible', True)
        else:
            # フォームデータからも取得できるように
            is_visible = request.POST.get('is_visible', 'true').lower() == 'true'
        
        review.is_visible = is_visible
        review.save()
        
        return JsonResponse({
            'success': True, 
            'message': f'レビューを{"表示" if is_visible else "非表示"}に変更しました。',
            'is_visible': review.is_visible
        })
    except json.JSONDecodeError as e:
        return JsonResponse({'success': False, 'error': f'JSONパースエラー: {str(e)}'})
    except Review.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'レビューが見つかりません'})
    except Exception as e:
        return JsonResponse({'success': False, 'error': f'エラーが発生しました: {str(e)}'})


@login_required
@user_passes_test(lambda u: u.manager_flag)
@require_POST
def delete_review(request, pk):
    """レビュー削除"""
    try:
        review = get_object_or_404(Review, pk=pk)
        shop_name = review.shop.name
        user_email = review.user.email if review.user else "匿名ユーザー"
        
        review.delete()
        
        return JsonResponse({
            'success': True,
            'message': f'{shop_name}の{user_email}のレビューを削除しました。'
        })
    except Review.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'レビューが見つかりません'})
    except Exception as e:
        return JsonResponse({'success': False, 'error': f'削除エラー: {str(e)}'})


# デバッグ用のAJAXテスト関数も追加
@login_required
@user_passes_test(lambda u: u.manager_flag)
def ajax_test(request):
    """AJAX通信のテスト用エンドポイント"""
    if request.method == 'POST':
        return JsonResponse({
            'success': True,
            'message': 'AJAX通信が正常に動作しています',
            'csrf_token': request.META.get('HTTP_X_CSRFTOKEN', 'なし'),
            'method': request.method
        })
    return JsonResponse({'success': False, 'error': 'POST method required'})


class SalesListView(AdminRequiredMixin, ListView):
    """売上一覧"""
    model = History
    template_name = 'admin_panel/sales_list.html'
    context_object_name = 'sales'
    paginate_by = 20
    
    def get_queryset(self):
        queryset = History.objects.select_related('user', 'shop')
        
        # 検索
        search = self.request.GET.get('search')
        if search:
            queryset = queryset.filter(shop__name__icontains=search)
        
        # 期間フィルター
        date_from = self.request.GET.get('date_from')
        date_to = self.request.GET.get('date_to')
        
        if date_from:
            try:
                start = datetime.strptime(date_from, '%Y-%m-%d').date()
                queryset = queryset.filter(date__gte=start)
            except ValueError:
                pass
        
        if date_to:
            try:
                end = datetime.strptime(date_to, '%Y-%m-%d').date()
                queryset = queryset.filter(date__lte=end)
            except ValueError:
                pass
        
        # ソート
        sort = self.request.GET.get('sort', '-date')
        queryset = queryset.order_by(sort)
        
        return queryset
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # 統計情報
        context['total_reservations'] = History.objects.count()
        context['today_reservations'] = History.objects.filter(date=timezone.now().date()).count()
        context['this_month_reservations'] = History.objects.filter(
            date__month=timezone.now().month,
            date__year=timezone.now().year
        ).count()
        context['total_people'] = History.objects.aggregate(Sum('number_of_people'))['number_of_people__sum'] or 0
        
        # 月別統計 (過去12ヶ月)
        monthly_stats = []
        for i in range(12):
            date = timezone.now().date().replace(day=1) - timedelta(days=30*i)
            count = History.objects.filter(
                date__month=date.month,
                date__year=date.year
            ).count()
            monthly_stats.append({
                'month': date.month,
                'count': count
            })
        context['monthly_stats'] = reversed(monthly_stats)
        
        # 人気店舗ランキング (予約数順)
        popular_shops = Shop.objects.annotate(
            reservation_count=Count('histories'),
            total_people=Sum('histories__number_of_people')
        ).filter(reservation_count__gt=0).order_by('-reservation_count')[:10]
        context['popular_shops'] = popular_shops
        
        return context
