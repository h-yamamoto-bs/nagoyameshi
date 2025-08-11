from django.shortcuts import render, get_object_or_404
from .models import Shop, Review, Favorite
from django.views.generic import ListView, DetailView
from django.db.models import Q, Avg
from django.http import JsonResponse
from django.contrib.auth.decorators import login_required
from django.views.decorators.csrf import csrf_exempt, ensure_csrf_cookie
from django.views.decorators.http import require_POST
from django.template.loader import render_to_string
from django.middleware.csrf import get_token

class ShopListView(ListView):
    model = Shop
    template_name = 'shops/shop_list.html'
    context_object_name = 'shops'
    paginate_by = 10
    
    def dispatch(self, request, *args, **kwargs):
        # CSRFトークンを確実に生成
        get_token(request)
        return super().dispatch(request, *args, **kwargs)
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # 各店舗のお気に入り情報を追加
        shops_with_favorites = []
        for shop in context['shops']:
            shop_data = {
                'shop': shop,
                'is_favorited': False,
                'favorite_count': shop.favorites.count()
            }
            
            if self.request.user.is_authenticated:
                shop_data['is_favorited'] = Favorite.objects.filter(
                    shop=shop,
                    user=self.request.user
                ).exists()
            
            shops_with_favorites.append(shop_data)
        
        context['shops_with_favorites'] = shops_with_favorites
        return context


class ShopDetailView(DetailView):
    model = Shop
    template_name = 'shops/shop_detail.html'
    context_object_name = 'shop'
    
    def dispatch(self, request, *args, **kwargs):
        # CSRFトークンを確実に生成
        get_token(request)
        return super().dispatch(request, *args, **kwargs)
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        shop = self.get_object()
        
        # ログイン済みユーザーのお気に入り状態をチェック
        if self.request.user.is_authenticated:
            context['is_favorited'] = Favorite.objects.filter(
                shop=shop,
                user=self.request.user
            ).exists()
        else:
            context['is_favorited'] = False
            
        # お気に入り数を追加
        context['favorite_count'] = shop.favorites.count()
        
        return context

class ShopSearchView(ListView):
    model = Shop
    template_name = 'shops/shop_search.html'
    context_object_name = 'shops'
    paginate_by = 10
    
    def dispatch(self, request, *args, **kwargs):
        # CSRFトークンを確実に生成
        get_token(request)
        return super().dispatch(request, *args, **kwargs)

    def get_queryset(self):

        # GETパラメーターから検索キーワードqを取得
        query = self.request.GET.get('q').strip()

        # 検索キーワードがからの場合
        if not query:
            return Shop.objects.none()
        
        # 検索
        # Qオブジェクトを使用して、name, address, phone_numberのいずれかにキーワードが含まれるShopを検索
        # また、prefetch_relatedを使用してimagesを事前に取得
        return Shop.objects.filter(
            Q(name__icontains=query) |
            Q(address__icontains=query) |
            Q(phone_number__icontains=query)
        ).prefetch_related('images').distinct()

    def get_context_data(self, **kwargs):

        # 親クラスのコンテキストを取得
        context = super().get_context_data(**kwargs)
        # print(**kwargs.get('shop_pk'))

        # 検索キーワードをコンテキストに追加
        # テンプレートで検索ボックスに前回の検索語を
        query = self.request.GET.get('q', '')
        context['query'] = query

        # 検索結果の総件数を追加
        # ページネーション情報とは別に総件数を表示するため
        context['result_count'] = self.get_queryset().count()

        # お気に入り情報を含む店舗データを準備
        shops = context['shops']
        shops_with_favorites = []
        
        for shop in shops:
            is_favorited = False
            favorite_count = shop.favorites.count()
            
            if self.request.user.is_authenticated:
                is_favorited = shop.favorites.filter(user=self.request.user).exists()
            
            shops_with_favorites.append({
                'shop': shop,
                'is_favorited': is_favorited,
                'favorite_count': favorite_count,
            })
        
        context['shops_with_favorites'] = shops_with_favorites

        return context


class ReviewListView(ListView):
    model = Review
    template_name = 'shops/review_list.html'
    context_object_name = 'reviews'
    paginate_by = 10
    ordering = ['-created_at']

    def get_queryset(self):
        # 特定の店舗のレビューを取得する場合
        shop_id = self.kwargs.get('shop_pk')
        if shop_id:
            return Review.objects.filter(shop_id=shop_id).select_related('user', 'shop').order_by('-created_at')
        
        # 全店舗のレビュー一覧
        return Review.objects.select_related('user', 'shop').order_by('-created_at')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # 特定の店舗の場合、店舗情報を追加
        shop_id = self.kwargs.get('shop_pk')
        if shop_id:
            try:
                shop = Shop.objects.get(pk=shop_id)
                context['shop'] = shop
                
                # その店舗の統計情報を追加
                reviews = self.get_queryset()
                if reviews:
                    context['review_stats'] = {
                        'total_count': reviews.count(),
                        'average_rating': reviews.aggregate(avg=Avg('rating'))['avg'] or 0,
                        'rating_distribution': {
                            i: reviews.filter(rating=i).count() for i in range(1, 6)
                        }
                    }
                else:
                    context['review_stats'] = {
                        'total_count': 0,
                        'average_rating': 0,
                        'rating_distribution': {i: 0 for i in range(1, 6)}
                    }
            except Shop.DoesNotExist:
                context['shop'] = None
        
        return context


@login_required
@require_POST
def submit_review(request):
    try:
        # POSTデータの取得
        shop_id = request.POST.get('shop_id')
        rating = request.POST.get('rating')
        comment = request.POST.get('comment', '')

        # バリデーション
        if not shop_id or not rating:
            return JsonResponse({
                'success': False,
                'message': '必要な情報が不足しています。'
            }, status=400)

        # 店舗の存在確認
        try:
            shop = Shop.objects.get(pk=shop_id)
        except Shop.DoesNotExist:
            return JsonResponse({
                'success': False,
                'message': '指定された店舗が見つかりません。'
            }, status=404)

        # 評価の範囲チェック
        try:
            rating = int(rating)
            if rating < 1 or rating > 5:
                raise ValueError
        except ValueError:
            return JsonResponse({
                'success': False,
                'message': '評価は1-5の範囲で入力してください。'
            }, status=400)

        # レビューの作成または更新
        review, created = Review.objects.update_or_create(
            shop=shop,
            user=request.user,
            defaults={
                'rating': rating,
                'comment': comment
            }
        )

        # 成功レスポンス
        return JsonResponse({
            'success': True,
            'message': 'レビューが正常に投稿されました。' if created else 'レビューが更新されました。',
            'review': {
                'id': review.id,
                'rating': review.rating,
                'comment': review.comment,
                'created_at': review.created_at.strftime('%Y-%m-%d %H:%M')
            }
        })

    except Exception as e:
        return JsonResponse({
            'success': False,
            'message': 'サーバーエラーが発生しました。'
        }, status=500)


# =================================== #
# お気に入り機能
# =================================== #

@login_required
@require_POST
def toggle_favorite(request, shop_id):
    """お気に入りの追加・削除を切り替える"""
    print(f"toggle_favorite called: user={request.user.email}, shop_id={shop_id}")
    print(f"Request headers: {dict(request.headers)}")
    print(f"CSRF token from request: {request.META.get('HTTP_X_CSRFTOKEN', 'Not found')}")
    print(f"Session key: {request.session.session_key}")
    
    try:
        shop = get_object_or_404(Shop, id=shop_id)
        print(f"Shop found: {shop.name}")
        
        # データベースアクセスを改良されたトランザクション内で実行
        from django.db import transaction
        import time
        
        max_retries = 3
        retry_delay = 0.1  # 100ms
        
        for attempt in range(max_retries):
            try:
                with transaction.atomic():
                    # 現在のお気に入り状態を確認
                    favorite_obj = Favorite.objects.filter(shop=shop, user=request.user).first()
                    print(f"Attempt {attempt + 1}: Favorite exists: {favorite_obj is not None}")
                    
                    if favorite_obj:
                        # 既にお気に入りに追加されている場合は削除
                        favorite_obj.delete()
                        print("Favorite removed")
                        is_favorited = False
                        message = 'お気に入りから削除しました。'
                    else:
                        # 新しくお気に入りに追加
                        new_favorite = Favorite.objects.create(shop=shop, user=request.user)
                        print(f"Favorite created with ID: {new_favorite.id}")
                        is_favorited = True
                        message = 'お気に入りに追加しました。'
                    
                    # お気に入り数を取得
                    favorite_count = shop.favorites.count()
                    print(f"Favorite count: {favorite_count}")
                    
                    # 成功した場合、ループを抜ける
                    break
                    
            except Exception as e:
                if "database is locked" in str(e) and attempt < max_retries - 1:
                    print(f"Database locked on attempt {attempt + 1}, retrying in {retry_delay}s...")
                    time.sleep(retry_delay)
                    retry_delay *= 2  # 指数バックオフ
                    continue
                else:
                    # 最後の試行または別のエラーの場合は例外を再発生
                    raise
        
        response_data = {
            'success': True,
            'message': message,
            'is_favorited': is_favorited,
            'favorite_count': favorite_count
        }
        print(f"Returning response: {response_data}")
        
        return JsonResponse(response_data)
        
    except Exception as e:
        import traceback
        error_details = traceback.format_exc()
        print(f"Error in toggle_favorite: {e}")
        print(f"Full traceback: {error_details}")
        return JsonResponse({
            'success': False,
            'message': 'サーバーエラーが発生しました。'
        }, status=500)

def load_more_shops(request):
    """追加の店舗データを読み込むAJAXエンドポイント"""
    print(f"load_more_shops called with request: {request.method}")
    print(f"GET params: {request.GET}")
    
    try:
        offset = int(request.GET.get('offset', 0))
        limit = 10
        print(f"Offset: {offset}, Limit: {limit}")
        
        shops = Shop.objects.all()[offset:offset + limit]
        print(f"Found {len(shops)} shops")
        shops_data = []
        
        for shop in shops:
            # お気に入り状態とカウントを取得
            is_favorited = False
            if request.user.is_authenticated:
                is_favorited = Favorite.objects.filter(
                    shop=shop,
                    user=request.user
                ).exists()
            
            favorite_count = shop.favorites.count()
            
            # 画像URLを取得
            image_url = ''
            if shop.images.exists():
                image_url = shop.images.first().image.url
            
            shops_data.append({
                'id': shop.pk,
                'name': shop.name,
                'address': shop.address,
                'seat_count': shop.seat_count,
                'image_url': image_url,
                'is_favorited': is_favorited,
                'favorite_count': favorite_count,
            })
        
        has_more = Shop.objects.count() > offset + limit
        
        response_data = {
            'success': True,
            'shops': shops_data,
            'has_more': has_more,
            'total_count': Shop.objects.count()
        }
        print(f"Returning response: {response_data}")
        
        return JsonResponse(response_data)
        
    except Exception as e:
        print(f"Error in load_more_shops: {e}")
        return JsonResponse({
            'success': False,
            'message': 'データの読み込みに失敗しました。'
        }, status=500)