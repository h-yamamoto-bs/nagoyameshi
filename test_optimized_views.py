import os
import sys
import django
from django.conf import settings

# パスとDjango設定
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'nagoyameshi.settings')
django.setup()

from django.db import connection, reset_queries
from django.test import Client
from django.contrib.auth import get_user_model

User = get_user_model()

def measure_performance(page_name, url, user=None):
    """ページのパフォーマンスを測定"""
    client = Client()
    
    if user:
        client.force_login(user)
    
    # クエリログをクリア
    reset_queries()
    
    # ページアクセス
    response = client.get(url)
    
    # 結果を表示
    print(f"\n=== {page_name} 最適化後テスト ===")
    print(f"URL: {url}")
    print(f"ステータス: {response.status_code}")
    print(f"DBクエリ数: {len(connection.queries)}")
    
    if len(connection.queries) <= 5:
        print("✅ クエリ数が5以下で最適化済み")
    elif len(connection.queries) <= 10:
        print("⚠️ クエリ数は改善されたが更なる最適化が可能")
    else:
        print("❌ まだ最適化が必要")
    
    # 最初の5クエリを表示
    print("主要なクエリ:")
    for i, query in enumerate(connection.queries[:5], 1):
        sql = query['sql'][:80] + "..." if len(query['sql']) > 80 else query['sql']
        print(f"  {i}. {sql}")
    
    if len(connection.queries) > 5:
        print(f"  ... (他に{len(connection.queries) - 5}個のクエリ)")
    
    return len(connection.queries)

def main():
    print("=== メインアプリビュー最適化テスト ===")
    
    # テスト用ユーザー取得
    try:
        regular_user = User.objects.filter(manager_flag=False).first()
        subscriber = User.objects.filter(manager_flag=False, subscription__is_active=True).first()
    except:
        print("テスト用ユーザーが見つかりません")
        return
    
    # テスト実行
    results = {}
    
    # 1. 店舗一覧（非ログイン）
    results['shop_list'] = measure_performance("店舗一覧（最適化後）", "/shops/shop_list/")
    
    # 2. 店舗詳細
    results['shop_detail'] = measure_performance("店舗詳細（最適化後）", "/shops/shop_1/")
    
    # 3. 店舗検索
    results['shop_search'] = measure_performance("店舗検索（最適化後）", "/shops/search/")
    
    # 4. マイページ（要ログイン）
    if regular_user:
        results['mypage'] = measure_performance("マイページ（最適化後）", "/accounts/mypage/", regular_user)
    
    # 5. レビュー一覧（要ログイン）
    if subscriber:
        results['reviews'] = measure_performance("レビュー一覧（最適化後）", "/shops/reviews/", subscriber)
    
    # 最適化結果のサマリー
    print("\n" + "="*60)
    print("最適化結果サマリー")
    print("="*60)
    
    for page, count in results.items():
        status = "✅ 良好" if count <= 5 else "⚠️ 改善" if count <= 10 else "❌ 要最適化"
        print(f"{page:20}: {count:2}クエリ {status}")
    
    avg_queries = sum(results.values()) / len(results)
    print(f"\n平均クエリ数: {avg_queries:.1f}")
    
    if avg_queries <= 10:
        print("✅ 全体的に良好な最適化レベルです")
    else:
        print("⚠️ 更なる最適化が推奨されます")

if __name__ == "__main__":
    main()
