from django.urls import path
from . import views

app_name = 'admin_panel'

urlpatterns = [
    # 認証
    path('login/', views.AdminLoginView.as_view(), name='login'),
    path('logout/', views.AdminLogoutView.as_view(), name='logout'),
    
    # ダッシュボード
    path('', views.AdminDashboardView.as_view(), name='dashboard'),
    
    # 会社情報
    path('company/', views.CompanyInfoView.as_view(), name='company_info'),
    
    # 店舗管理
    path('shops/', views.ShopListView.as_view(), name='shop_list'),
    path('shops/create/', views.ShopCreateView.as_view(), name='shop_create'),
    path('shops/<int:pk>/', views.ShopDetailView.as_view(), name='shop_detail'),
    path('shops/<int:pk>/edit/', views.ShopEditView.as_view(), name='shop_edit'),
    path('shops/<int:pk>/delete/', views.ShopDeleteView.as_view(), name='shop_delete'),
    path('shops/csv-export/', views.shop_csv_export, name='shop_csv_export'),
    path('shops/csv-import/', views.shop_csv_import, name='shop_csv_import'),
    
    # 会員管理
    path('users/', views.UserListView.as_view(), name='user_list'),
    path('users/create/', views.UserCreateView.as_view(), name='user_create'),
    path('users/<int:pk>/edit/', views.UserEditView.as_view(), name='user_edit'),
    path('users/<int:pk>/delete/', views.UserDeleteView.as_view(), name='user_delete'),
    path('users/<int:pk>/detail/', views.UserDetailView.as_view(), name='user_detail'),
    path('users/csv-export/', views.user_csv_export, name='user_csv_export'),
    
    # カテゴリ管理
    path('categories/', views.CategoryListView.as_view(), name='category_list'),
    path('categories/<int:category_id>/shops/', views.CategoryShopsView.as_view(), name='category_shops'),
    path('categories/create/', views.CategoryCreateView.as_view(), name='category_create'),
    path('categories/<int:pk>/edit/', views.CategoryEditView.as_view(), name='category_edit'),
    path('categories/<int:pk>/delete/', views.CategoryDeleteView.as_view(), name='category_delete'),
    
    # レビュー管理
    path('reviews/', views.ReviewListView.as_view(), name='review_list'),
    path('reviews/<int:pk>/toggle/', views.toggle_review_visibility, name='toggle_review_visibility'),
    path('reviews/<int:pk>/delete/', views.delete_review, name='delete_review'),
    path('ajax-test/', views.ajax_test, name='ajax_test'),
    
    # 売上管理
    path('sales/', views.SalesListView.as_view(), name='sales_list'),
]
