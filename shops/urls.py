from django.urls import path
from . import views

app_name = 'shops'

urlpatterns = [
    path('shop_list/', views.ShopListView.as_view(), name='shop_list'),
    path('shop_<int:pk>/', views.ShopDetailView.as_view(), name='shop_detail'),
    path('search/', views.ShopSearchView.as_view(), name='search'),
    path('review/submit/', views.submit_review, name='submit_review'),
    path('reviews/', views.ReviewListView.as_view(), name='review_list'),
    path('shop_<int:shop_pk>/reviews/', views.ReviewListView.as_view(), name='shop_review_list'),
    # お気に入り機能
    path('favorite/toggle/<int:shop_id>/', views.toggle_favorite, name='toggle_favorite'),
    # 追加読み込み機能
    path('api/load-more-shops/', views.load_more_shops, name='load_more_shops'),
    # 予約作成
    path('reserve/', views.create_reservation, name='create_reservation'),
]
