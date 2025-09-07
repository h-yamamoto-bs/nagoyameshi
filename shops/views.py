from django.shortcuts import render, get_object_or_404, redirect
from .models import Shop, Review, Favorite, Category, ShopCategory, History
from django.views.generic import ListView, DetailView
from django.db.models import Q, Avg, Count, Exists, OuterRef, Prefetch
from django.http import JsonResponse
from django.contrib.auth.decorators import login_required
from django.views.decorators.csrf import csrf_exempt, ensure_csrf_cookie
from django.views.decorators.http import require_POST
from django.template.loader import render_to_string
from django.middleware.csrf import get_token
from datetime import datetime
from django.db import transaction
from django.contrib import messages
from accounts.decorators import subscription_required
from accounts.models import Subscription

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
        """N+1クエリを防ぐため、必要なデータを一度で取得"""
        queryset = Shop.objects.select_related().prefetch_related(
            'images',
            Prefetch('categories', queryset=ShopCategory.objects.select_related('category'))
        ).annotate(
            favorite_count=Count('favorites', distinct=True)
        )
        
        # ログイン済みユーザーの場合、お気に入り状態も一緒に取得
        if self.request.user.is_authenticated:
            user_favorite_subquery = Favorite.objects.filter(
                shop=OuterRef('pk'),
                user=self.request.user
            )
            queryset = queryset.annotate(
                is_favorited=Exists(user_favorite_subquery)
            )
        
        return queryset.order_by(self.ordering[0])
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # 最適化後：各店舗のデータは既にクエリセットに含まれている
        shops = context['shops']
        shops_with_favorites = []
        
        for shop in shops:
            # prefetchされた画像リストから最初の画像を取得（追加クエリなし）
            images_list = list(shop.images.all())
            first_image = images_list[0] if images_list else None
            image_count = len(images_list)
            
            shop_data = {
                'shop': shop,
                'is_favorited': getattr(shop, 'is_favorited', False) if self.request.user.is_authenticated else False,
                'favorite_count': shop.favorite_count,  # annotateされた値を使用
                'categories': shop.categories.all(),  # prefetchされたデータを使用
                'first_image': first_image,  # 最初の画像を事前計算
                'image_count': image_count,  # 画像数を事前計算
                'has_images': image_count > 0,  # 画像存在フラグ
            }
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
    
    def get_queryset(self):
        """関連データを一度で取得してN+1クエリを防ぐ"""
        return Shop.objects.select_related().prefetch_related(
            'images',
            Prefetch('categories', queryset=ShopCategory.objects.select_related('category')),
            Prefetch('reviews', queryset=Review.objects.select_related('user').order_by('-created_at'))
        ).annotate(
            favorite_count=Count('favorites', distinct=True),
            review_count=Count('reviews', distinct=True),
            avg_rating=Avg('reviews__rating')
        )
    
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
            
        # annotateされた値を使用（個別クエリを避ける）
        context['favorite_count'] = shop.favorite_count
        
        # 店舗のカテゴリー情報（prefetchされたデータを使用）
        context['shop_categories'] = shop.categories.all()
        
        # レビュー関連の情報（prefetchされたデータを使用）
        reviews = shop.reviews.all()  # 既にorder_byされている
        context['reviews'] = reviews
        context['review_count'] = shop.review_count  # annotateされた値を使用
        
        # 平均評価を計算（annotateされた値を使用）
        avg_rating = shop.avg_rating
        context['avg_rating'] = round(avg_rating, 1) if avg_rating else 0
        context['avg_rating_int'] = int(avg_rating) if avg_rating else 0
        
        # ログイン済みユーザーの既存レビューをチェック
        if self.request.user.is_authenticated:
            # prefetchされたレビューから検索（追加クエリなし）
            user_review = None
            for review in reviews:
                if review.user_id == self.request.user.id:
                    user_review = review
                    break
            context['user_review'] = user_review
        else:
            context['user_review'] = None

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
        # GETパラメーターから検索キーワードqを取得
        query = self.request.GET.get('q')
        category_id = self.request.GET.get('category')

        # 検索条件の準備 - N+1クエリを防ぐため必要なデータを一度で取得
        queryset = Shop.objects.select_related().prefetch_related(
            'images',
            Prefetch('categories', queryset=ShopCategory.objects.select_related('category'))
        ).annotate(
            favorite_count=Count('favorites', distinct=True)
        )

        # ログイン済みユーザーの場合、お気に入り状態も一緒に取得
        if self.request.user.is_authenticated:
            user_favorite_subquery = Favorite.objects.filter(
                shop=OuterRef('pk'),
                user=self.request.user
            )
            queryset = queryset.annotate(
                is_favorited=Exists(user_favorite_subquery)
            )

        # カテゴリー検索の場合
        if category_id:
            queryset = queryset.filter(categories__category_id=category_id).distinct()
        
        # キーワード検索の場合
        elif query and query.strip():
            query = query.strip()
            queryset = queryset.filter(
                Q(name__icontains=query) |
                Q(address__icontains=query) |
                Q(phone_number__icontains=query) |
                Q(categories__category__name__icontains=query)  # カテゴリー名でも検索
            ).distinct()
        else:
            # 検索条件がない場合は全店舗を表示
            queryset = queryset.all()
        
        # ページネーション警告を解決するために順序を確実に指定
        return queryset.order_by('id')

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

        # 最適化後：各店舗のデータは既にクエリセットに含まれている
        shops = context['shops']
        shops_with_favorites = []
        
        for shop in shops:
            # prefetchされた画像リストから最初の画像を取得（追加クエリなし）
            images_list = list(shop.images.all())
            first_image = images_list[0] if images_list else None
            image_count = len(images_list)
            
            shop_data = {
                'shop': shop,
                'is_favorited': getattr(shop, 'is_favorited', False) if self.request.user.is_authenticated else False,
                'favorite_count': shop.favorite_count,  # annotateされた値を使用
                'categories': shop.categories.all(),  # prefetchされたデータを使用
                'first_image': first_image,  # 最初の画像を事前計算
                'image_count': image_count,  # 画像数を事前計算
                'has_images': image_count > 0,  # 画像存在フラグ
            }
            shops_with_favorites.append(shop_data)
        
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
                # Heroku用: メディアURLを静的ファイルURLに変換
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

            # 予約をHistoryに保存（履歴として管理）
            History.objects.create(
                shop=shop,
                user=request.user,
                date=reserve_date,
                number_of_people=people,
            )

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