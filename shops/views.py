from django.shortcuts import render, get_object_or_404, redirect
from .models import Shop, Review, Favorite, Category, ShopCategory, History
from django.views.generic import ListView, DetailView
from django.db.models import Q, Avg, Count, Exists, OuterRef, Prefetch, Case, When, IntegerField
from django.http import JsonResponse
from django.contrib.auth.decorators import login_required
from django.views.decorators.csrf import csrf_exempt, ensure_csrf_cookie
from django.views.decorators.http import require_POST
from django.template.loader import render_to_string
from django.middleware.csrf import get_token
from datetime import datetime
from django.db import transaction
from django.core.cache import cache
from django.contrib import messages
from accounts.decorators import subscription_required
from accounts.models import Subscription
from accounts.email_utils import send_reservation_mail
from django.core.cache import cache

class ShopListView(ListView):
    model = Shop
    template_name = 'shops/shop_list.html'
    context_object_name = 'shops'
    paginate_by = 10
    ordering = ['id']  # ページネーション警告を解決するための順序指定
    
    def dispatch(self, request, *args, **kwargs):
        # CSRFトークンを確実に生成
        get_token(request)
        return super().dispatch(request, *args, **kwargs)
    
    def get_queryset(self):
        """一覧用QuerySetに集計と関連データを事前付与し、人気順(お気に入り数降順)で返す。"""
        # キャッシュキーを生成
        cache_key = f"shop_list_user_{self.request.user.id if self.request.user.is_authenticated else 'anonymous'}"
        cached_result = cache.get(cache_key)
        
        if cached_result:
            return cached_result
            
        # 最適化されたクエリ
        qs = (Shop.objects
              .select_related('user')
              .prefetch_related(
                  'images',
                  'categories__category'
              ))
        
        # 集計データを一回で取得
        qs = qs.annotate(
            favorite_count=Count('favorites', distinct=True),
            review_count=Count('reviews', distinct=True)
        )
        
        # ログインユーザーのお気に入り状態
        if self.request.user.is_authenticated:
            fav_sub = Favorite.objects.filter(user=self.request.user, shop=OuterRef('pk'))
            qs = qs.annotate(is_favorited=Exists(fav_sub))
        
        # 人気順 -> 同数時はid昇順で安定
        qs = qs.order_by('-favorite_count', 'id')
        
        # 結果をキャッシュ（5分間）
        cache.set(cache_key, qs, 300)
        return qs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        shops_with_favorites = []
        for shop in context['shops']:
            # annotateで付与済みならそれを利用 / 無ければ従来通りフォールバック（安全）
            favorite_count = getattr(shop, 'favorite_count', None)
            if favorite_count is None:
                favorite_count = shop.favorites.count()
            if self.request.user.is_authenticated:
                is_favorited = getattr(shop, 'is_favorited', None)
                if is_favorited is None:
                    is_favorited = Favorite.objects.filter(shop=shop, user=self.request.user).exists()
            else:
                is_favorited = False

            # カテゴリーはprefetch済み
            categories_list = []
            for shop_category in shop.categories.all():
                categories_list.append(shop_category.category)
            
            # メイン画像をprefetch済みデータから取得（N+1問題を回避）
            main_image_url = None
            if hasattr(shop, '_prefetched_objects_cache') and 'images' in shop._prefetched_objects_cache:
                images = shop._prefetched_objects_cache['images']
                if images:
                    main_image_url = images[0].image.url
            else:
                # fallback
                first_image = shop.images.first()
                if first_image:
                    main_image_url = first_image.image.url

            shops_with_favorites.append({
                'shop': shop,
                'is_favorited': is_favorited,
                'favorite_count': favorite_count,
                'categories': categories_list,
                'main_image_url': main_image_url,
            })

        context['shops_with_favorites'] = shops_with_favorites
        context['categories'] = Category.objects.all()
        return context


class ShopDetailView(DetailView):
    model = Shop
    template_name = 'shops/shop_detail.html'
    context_object_name = 'shop'
    
    def dispatch(self, request, *args, **kwargs):
        # CSRFトークンを確実に生成
        get_token(request)
        return super().dispatch(request, *args, **kwargs)
    
    def get_object(self, queryset=None):
        """最適化されたオブジェクト取得 - 一回のクエリで全情報取得"""
        if queryset is None:
            queryset = self.get_queryset()
        
        pk = self.kwargs.get(self.pk_url_kwarg)
        if pk is None:
            raise ValueError("Shop ID is required")
        
        # 全ての関連データを一度に取得し、集計も含める
        try:
            shop = (Shop.objects
                    .select_related('user')
                    .prefetch_related(
                        'images',
                        'categories__category',
                        Prefetch('reviews', queryset=Review.objects.select_related('user').order_by('-created_at')),
                        'favorites'
                    )
                    .annotate(
                        favorite_count=Count('favorites', distinct=True),
                        review_count=Count('reviews', distinct=True),
                        avg_rating=Avg('reviews__rating')
                    )
                    .get(pk=pk))
            return shop
        except Shop.DoesNotExist:
            from django.http import Http404
            raise Http404("Shop not found")
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        shop = context['shop']  # get_object()は既に呼ばれている
        
        # アノテーション済みデータを使用（追加クエリなし）
        context['favorite_count'] = getattr(shop, 'favorite_count', 0)
        context['review_count'] = getattr(shop, 'review_count', 0)
        avg_rating = getattr(shop, 'avg_rating', 0) or 0
        context['avg_rating'] = round(avg_rating, 1)
        context['avg_rating_int'] = int(avg_rating)
        
        # prefetch済みレビューデータを使用（追加クエリなし）
        reviews = list(shop.reviews.all())
        context['reviews'] = reviews
        
        # ログインユーザー関連：効率化
        if self.request.user.is_authenticated:
            # prefetch済みお気に入りデータから検索
            context['is_favorited'] = any(
                fav.user_id == self.request.user.id for fav in shop.favorites.all()
            )
            # prefetch済みレビューから検索
            context['user_review'] = next(
                (r for r in reviews if r.user_id == self.request.user.id), None
            )
        else:
            context['is_favorited'] = False
            context['user_review'] = None
            
        # 店舗カテゴリ情報（prefetch済み）
        context['shop_categories'] = shop.categories.all()

        # サブスクリプション状態（予約フォームの表示制御に使用）
        can_reserve = False
        if self.request.user.is_authenticated:
            try:
                sub = self.request.user.subscription
                has_valid_stripe = bool(getattr(sub, 'stripe_subscription_id', None))
                can_reserve = bool(getattr(sub, 'is_active', False) and has_valid_stripe)
            except Subscription.DoesNotExist:
                can_reserve = False
        context['can_reserve'] = can_reserve
        # レビュー編集/投稿など他のプレミアム機能の制御にも使えるフラグ
        context['is_subscriber'] = can_reserve

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
        # GETパラメーターから検索キーワード/カテゴリー
        query = self.request.GET.get('q')
        category_id = self.request.GET.get('category')

        qs = Shop.objects.all().prefetch_related('images', 'categories__category')

        if category_id:
            qs = qs.filter(categories__category_id=category_id)
        elif query and query.strip():
            q = query.strip()
            qs = qs.filter(
                Q(name__icontains=q) |
                Q(address__icontains=q) |
                Q(phone_number__icontains=q) |
                Q(categories__category__name__icontains=q)
            )

        qs = qs.order_by('id').distinct()

        # 共通最適化: お気に入り数 & ログイン済み判定
        qs = qs.annotate(favorite_count=Count('favorites'))
        if self.request.user.is_authenticated:
            fav_sub = Favorite.objects.filter(user=self.request.user, shop=OuterRef('pk'))
            qs = qs.annotate(is_favorited=Exists(fav_sub))
        return qs

    def get_context_data(self, **kwargs):
        # 親クラスのコンテキストを取得
        context = super().get_context_data(**kwargs)

        # 検索キーワードとカテゴリーをコンテキストに追加
        query = self.request.GET.get('q', '')
        category_id = self.request.GET.get('category', '')
        context['query'] = query
        context['selected_category'] = category_id

        # 検索されたカテゴリー情報を追加
        if category_id:
            try:
                context['category_name'] = Category.objects.get(id=category_id).name
            except Category.DoesNotExist:
                context['category_name'] = ''

        # 検索結果の総件数を追加
        result_count = self.get_queryset().count()
        context['result_count'] = result_count

        # お気に入り/カテゴリー情報（annotate + prefetch フォールバック対応）
        shops_with_favorites = []
        for shop in context['shops']:
            favorite_count = getattr(shop, 'favorite_count', None)
            if favorite_count is None:
                favorite_count = shop.favorites.count()
            if self.request.user.is_authenticated:
                is_favorited = getattr(shop, 'is_favorited', None)
                if is_favorited is None:
                    is_favorited = Favorite.objects.filter(shop=shop, user=self.request.user).exists()
            else:
                is_favorited = False
                
            # メイン画像をprefetch済みデータから取得
            main_image_url = None
            if hasattr(shop, '_prefetched_objects_cache') and 'images' in shop._prefetched_objects_cache:
                images = shop._prefetched_objects_cache['images']
                if images:
                    main_image_url = images[0].image.url
            else:
                first_image = shop.images.first()
                if first_image:
                    main_image_url = first_image.image.url
                    
            shops_with_favorites.append({
                'shop': shop,
                'is_favorited': is_favorited,
                'favorite_count': favorite_count,
                'categories': shop.categories.all(),
                'main_image_url': main_image_url,
            })
        context['shops_with_favorites'] = shops_with_favorites
        context['categories'] = Category.objects.all()

        return context


class ReviewListView(ListView):
    model = Review
    template_name = 'shops/review_list.html'
    context_object_name = 'reviews'
    paginate_by = 20  # ページネーション強化
    ordering = ['-created_at']

    def get_queryset(self):
        # 特定の店舗のレビューを取得する場合
        shop_id = self.kwargs.get('shop_pk')
        if shop_id:
            return (Review.objects
                    .filter(shop_id=shop_id)
                    .select_related('user', 'shop')
                    .prefetch_related('shop__images')
                    .order_by('-created_at'))
        
        # 全店舗のレビュー一覧（最適化済み）
        return (Review.objects
                .select_related('user', 'shop')
                .prefetch_related('shop__images')
                .order_by('-created_at'))

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # 現在のページのレビューのみを処理（ページネーション対応）
        reviews_with_images = []
        for review in context['reviews']:  # ページネーション済みレビュー
            # shop画像をprefetch済みデータから効率的に取得
            main_image_url = None
            if hasattr(review.shop, '_prefetched_objects_cache') and 'images' in review.shop._prefetched_objects_cache:
                images = review.shop._prefetched_objects_cache['images']
                if images:
                    main_image_url = images[0].image.url
            else:
                # fallback（通常は不要）
                first_image = review.shop.images.first()
                if first_image:
                    main_image_url = first_image.image.url
            
            reviews_with_images.append({
                'review': review,
                'main_image_url': main_image_url,
            })
        
        context['reviews_with_images'] = reviews_with_images
        
        # 特定の店舗の場合のみ、統計情報を追加
        shop_id = self.kwargs.get('shop_pk')
        if shop_id:
            try:
                # 店舗情報を効率的に取得
                shop = (Shop.objects
                        .select_related('user')
                        .prefetch_related('images')
                        .get(pk=shop_id))
                context['shop'] = shop
                
                # 統計情報を効率的に計算（該当店舗のレビューのみ）
                review_stats = (Review.objects
                                .filter(shop_id=shop_id)
                                .aggregate(
                                    total_count=Count('id'),
                                    average_rating=Avg('rating'),
                                    rating_1=Count(Case(When(rating=1, then=1))),
                                    rating_2=Count(Case(When(rating=2, then=1))),
                                    rating_3=Count(Case(When(rating=3, then=1))),
                                    rating_4=Count(Case(When(rating=4, then=1))),
                                    rating_5=Count(Case(When(rating=5, then=1)))
                                ))
                
                context['review_stats'] = {
                    'total_count': review_stats['total_count'] or 0,
                    'average_rating': review_stats['average_rating'] or 0,
                    'rating_distribution': {
                        1: {
                            'count': review_stats['rating_1'],
                            'percentage': (review_stats['rating_1'] * 100 / review_stats['total_count']) if review_stats['total_count'] > 0 else 0
                        },
                        2: {
                            'count': review_stats['rating_2'],
                            'percentage': (review_stats['rating_2'] * 100 / review_stats['total_count']) if review_stats['total_count'] > 0 else 0
                        },
                        3: {
                            'count': review_stats['rating_3'], 
                            'percentage': (review_stats['rating_3'] * 100 / review_stats['total_count']) if review_stats['total_count'] > 0 else 0
                        },
                        4: {
                            'count': review_stats['rating_4'],
                            'percentage': (review_stats['rating_4'] * 100 / review_stats['total_count']) if review_stats['total_count'] > 0 else 0
                        },
                        5: {
                            'count': review_stats['rating_5'],
                            'percentage': (review_stats['rating_5'] * 100 / review_stats['total_count']) if review_stats['total_count'] > 0 else 0
                        }
                    }
                }
                
            except Shop.DoesNotExist:
                context['shop'] = None
                context['review_stats'] = {
                    'total_count': 0,
                    'average_rating': 0,
                    'rating_distribution': {i: 0 for i in range(1, 6)}
                }
        
        return context


@login_required
@subscription_required
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


@login_required
@subscription_required
@require_POST
def edit_review(request, review_id):
    """レビューの編集"""
    try:
        # レビューの取得（自分のレビューのみ）
        try:
            review = Review.objects.get(pk=review_id, user=request.user)
        except Review.DoesNotExist:
            return JsonResponse({
                'success': False,
                'message': 'レビューが見つかりません。'
            }, status=404)

        # POSTデータの取得
        rating = request.POST.get('rating')
        comment = request.POST.get('comment', '')

        # バリデーション
        if not rating:
            return JsonResponse({
                'success': False,
                'message': '評価を入力してください。'
            }, status=400)

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

        # レビューの更新
        review.rating = rating
        review.comment = comment
        review.save()

        # 成功レスポンス
        return JsonResponse({
            'success': True,
            'message': 'レビューが正常に更新されました。',
            'review': {
                'id': review.id,
                'rating': review.rating,
                'comment': review.comment,
                'created_at': review.created_at.strftime('%Y-%m-%d %H:%M'),
                'updated_at': review.updated_at.strftime('%Y-%m-%d %H:%M')
            }
        })

    except Exception as e:
        return JsonResponse({
            'success': False,
            'message': 'サーバーエラーが発生しました。'
        }, status=500)


@login_required
@require_POST
def delete_review(request, review_id):
    """レビューの削除"""
    try:
        # レビューの取得（自分のレビューのみ）
        try:
            review = Review.objects.get(pk=review_id, user=request.user)
        except Review.DoesNotExist:
            return JsonResponse({
                'success': False,
                'message': 'レビューが見つかりません。'
            }, status=404)

        # レビューの削除
        shop_name = review.shop.name
        review.delete()

        # 成功レスポンス
        return JsonResponse({
            'success': True,
            'message': f'{shop_name}のレビューを削除しました。'
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
@subscription_required
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
    """追加の店舗データを読み込むAJAXエンドポイント (N+1最適化版)"""
    print(f"load_more_shops called with request: {request.method}")
    print(f"GET params: {request.GET}")
    try:
        offset = int(request.GET.get('offset', 0))
        limit = 10
        print(f"Offset: {offset}, Limit: {limit}")

        base_qs = (Shop.objects
                    .all()
                    .order_by('id')
                    .prefetch_related('images'))
        # 集計
        base_qs = base_qs.annotate(favorite_count=Count('favorites'))
        if request.user.is_authenticated:
            fav_sub = Favorite.objects.filter(user=request.user, shop=OuterRef('pk'))
            base_qs = base_qs.annotate(is_favorited=Exists(fav_sub))

        shops = list(base_qs[offset:offset + limit])
        print(f"Found {len(shops)} shops")

        shops_data = []
        for shop in shops:
            favorite_count = getattr(shop, 'favorite_count', shop.favorites.count())
            if request.user.is_authenticated:
                is_favorited = getattr(shop, 'is_favorited', Favorite.objects.filter(shop=shop, user=request.user).exists())
            else:
                is_favorited = False

            # 画像（prefetch済み）
            images = list(shop.images.all())
            image_url = ''
            if images:
                image_url = images[0].image.url
                if image_url.startswith('/media/'):
                    image_url = image_url.replace('/media/', '/static/')

            shops_data.append({
                'id': shop.pk,
                'name': shop.name,
                'address': shop.address,
                'seat_count': shop.seat_count,
                'image_url': image_url,
                'is_favorited': is_favorited,
                'favorite_count': favorite_count,
            })

        total_count = Shop.objects.count()
        has_more = total_count > offset + limit
        response_data = {
            'success': True,
            'shops': shops_data,
            'has_more': has_more,
            'total_count': total_count,
        }
        print(f"Returning response: {response_data}")
        return JsonResponse(response_data)
    except Exception as e:
        print(f"Error in load_more_shops: {e}")
        return JsonResponse({'success': False, 'message': 'データの読み込みに失敗しました。'}, status=500)

@login_required
@subscription_required
@require_POST
def create_reservation(request):
    """予約作成: フォーム送信/ AJAX 両対応。残席不足ならエラー、成功で履歴作成。"""
    def is_ajax(req):
        return req.headers.get('x-requested-with') == 'XMLHttpRequest'

    try:
        shop_id = request.POST.get('shop_id')
        date_str = request.POST.get('date')  # 例: '2025-08-30'
        people_str = request.POST.get('people')

        # 入力チェック
        if not (shop_id and date_str and people_str):
            if is_ajax(request):
                return JsonResponse({'success': False, 'message': '必要な情報が不足しています。'}, status=400)
            messages.error(request, '必要な情報が不足しています。')
            return redirect('shops:shop_detail', pk=shop_id or 0)

        shop = get_object_or_404(Shop, pk=shop_id)

        # 型変換
        try:
            reserve_date = datetime.strptime(date_str, '%Y-%m-%d').date()
        except ValueError:
            if is_ajax(request):
                return JsonResponse({'success': False, 'message': '日付の形式が正しくありません。YYYY-MM-DDで指定してください。'}, status=400)
            messages.error(request, '日付の形式が正しくありません。YYYY-MM-DDで指定してください。')
            return redirect('shops:shop_detail', pk=shop.id)

        try:
            people = int(people_str)
            if people <= 0:
                raise ValueError
        except ValueError:
            if is_ajax(request):
                return JsonResponse({'success': False, 'message': '人数は1以上の整数で入力してください。'}, status=400)
            messages.error(request, '人数は1以上の整数で入力してください。')
            return redirect('shops:shop_detail', pk=shop.id)

        # 残席チェックと作成をトランザクションで
        with transaction.atomic():
            remaining = shop.remaining_seats_on(reserve_date)
            if people > remaining:
                if is_ajax(request):
                    return JsonResponse({'success': False, 'message': f'指定日の残席が不足しています。（残り {remaining} 席）'}, status=400)
                messages.error(request, f'指定日の残席が不足しています。（残り {remaining} 席）')
                return redirect('shops:shop_detail', pk=shop.id)

            # 予約保存
            History.objects.create(
                shop=shop,
                user=request.user,
                date=reserve_date,
                number_of_people=people,
            )

        # メール送信（失敗してもフロー継続）
        if request.user.email:
            send_reservation_mail(request.user, shop, reserve_date, people)

        if is_ajax(request):
            new_remaining = shop.remaining_seats_on(reserve_date)
            return JsonResponse({'success': True, 'message': '予約を受け付けました。', 'remaining_seats': new_remaining})

        messages.success(request, '予約を受け付けました。')
        return redirect('shops:shop_detail', pk=shop.id)

    except Exception:
        if is_ajax(request):
            return JsonResponse({'success': False, 'message': 'サーバーエラーが発生しました。'}, status=500)
        messages.error(request, 'サーバーエラーが発生しました。')
        return redirect('shops:shop_list')