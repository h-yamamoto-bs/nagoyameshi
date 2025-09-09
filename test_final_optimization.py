"""
メインアプリの大幅最適化テスト
テンプレートタグとビューの組み合わせ最適化
"""
import os
import sys
import django
from django.test import TestCase, Client, override_settings
from django.contrib.auth import get_user_model
from django.db import connection
from django.conf import settings

# Django設定のセットアップ
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'nagoyameshi.settings')
django.setup()

def print_query_summary(queries, url, test_name):
    """クエリサマリーを出力"""
    print(f"\n=== {test_name} ===")
    print(f"URL: {url}")
    print(f"DBクエリ数: {len(queries)}")
    
    if len(queries) <= 8:
        print("✅ 最適化済み")
    elif len(queries) <= 12:
        print("⚠️ クエリ数は改善されたが更なる最適化が可能")
    else:
        print("❌ まだ最適化が必要")
    
    if queries:
        print("主要なクエリ:")
        for i, query in enumerate(queries[:5], 1):
            query_str = query['sql'][:80] + "..." if len(query['sql']) > 80 else query['sql']
            print(f"  {i}. {query_str}")
        if len(queries) > 5:
            print(f"  ... (他に{len(queries) - 5}個のクエリ)")

def count_db_queries():
    """データベースクエリ数をカウント"""
    return len(connection.queries)

def test_main_app_final_optimization():
    print("=== メインアプリ最終最適化テスト ===")
    
    client = Client()
    User = get_user_model()
    
    # 一般ユーザーとサブスクライバーを作成
    if not User.objects.filter(manager_flag=False).exists():
        user = User.objects.create_user(
            email='user@example.com',
            password='password123'
        )
        print("一般ユーザーを作成")
    else:
        user = User.objects.filter(manager_flag=False).first()
        print("既存の一般ユーザーを使用")
    
    if not User.objects.filter(manager_flag=False, subscription__is_active=True).exists():
        from accounts.models import Subscription
        subscriber = User.objects.create_user(
            email='subscriber@example.com',
            password='password123'
        )
        Subscription.objects.create(
            user=subscriber,
            is_active=True,
            stripe_subscription_id='sub_test123'
        )
        print("サブスクライバーユーザーを作成")
    else:
        subscriber = User.objects.filter(manager_flag=False, subscription__is_active=True).first()
        print("既存のサブスクライバーユーザーを使用")
    
    # 各ページのテスト
    test_urls = [
        ('/shops/shop_list/', '店舗一覧（最終最適化後）'),
        ('/shops/shop_1/', '店舗詳細（最終最適化後）'),
        ('/shops/search/', '店舗検索（最終最適化後）'),
        ('/accounts/mypage/', 'マイページ（最終最適化後）'),
        ('/shops/reviews/', 'レビュー一覧（最終最適化後）'),
    ]
    
    results = {}
    
    for url, test_name in test_urls:
        # クエリカウントをリセット
        connection.queries_log.clear()
        initial_count = count_db_queries()
        
        if 'mypage' in url:
            # マイページは認証が必要
            client.login(email=subscriber.email, password='password123')
        
        try:
            response = client.get(url)
            final_count = count_db_queries()
            query_count = final_count - initial_count
            results[url] = query_count
            
            print_query_summary(
                connection.queries[initial_count:], 
                url, 
                f"{test_name} 最終最適化後テスト"
            )
            
        except Exception as e:
            print(f"エラー: {url} - {e}")
            results[url] = 999  # エラー時は高い値を設定
        
        client.logout()
    
    # 結果サマリー
    print("\n" + "="*60)
    print("最終最適化結果サマリー")
    print("="*60)
    
    total_queries = 0
    test_count = 0
    
    for url, query_count in results.items():
        test_name = url.split('/')[-2] if url.split('/')[-2] else url.split('/')[-3]
        if query_count < 999:
            total_queries += query_count
            test_count += 1
            
        status = "✅ 最適" if query_count <= 8 else "⚠️ 改善" if query_count <= 12 else "❌ 要最適化"
        print(f"{test_name:20} : {query_count}クエリ {status}")
    
    if test_count > 0:
        avg_queries = total_queries / test_count
        print(f"\n平均クエリ数: {avg_queries:.1f}")
        
        if avg_queries <= 8:
            print("✅ 優秀な最適化結果です")
        elif avg_queries <= 12:
            print("⚠️ 良好な最適化ですが、さらなる改善が可能です")
        else:
            print("⚠️ 更なる最適化が推奨されます")

if __name__ == "__main__":
    # デバッグ設定でクエリログを有効化
    settings.LOGGING['loggers']['django.db.backends'] = {
        'handlers': ['console'],
        'level': 'DEBUG',
    }
    
    # クエリログを有効化
    settings.DEBUG = True
    connection.queries_log.clear()
    
    test_main_app_final_optimization()
