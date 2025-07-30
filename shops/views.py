from django.shortcuts import render
from .models import Shop, Review
from django.views.generic import ListView, DetailView
from django.db.models import Q
from django.http import JsonResponse
from django.contrib.auth.decorators import login_required
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

class ShopListView(ListView):
    model = Shop
    template_name = 'shops/shop_list.html'
    context_object_name = 'shops'
    paginate_by = 10


class ShopDetailView(DetailView):
    model = Shop
    template_name = 'shops/shop_detail.html'
    context_object_name = 'shop'

class ShopSearchView(ListView):
    model = Shop
    template_name = 'shops/shop_search.html'
    context_object_name = 'shops'
    paginate_by = 10

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