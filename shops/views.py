from django.shortcuts import render
from .models import Shop
from django.views.generic import ListView, DetailView
from django.db.models import Q

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