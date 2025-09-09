#!/usr/bin/env python
"""
リクエスト数測定テスト
Herokuのリクエスト制限対策のため、各機能のリクエスト数を測定する
"""

import os
import sys
import django
import requests
import time
from collections import defaultdict

# Django設定を読み込む
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'nagoyameshi.settings')
django.setup()

# テスト用のALLOWED_HOSTSを設定
from django.conf import settings
if 'testserver' not in settings.ALLOWED_HOSTS:
    settings.ALLOWED_HOSTS.append('testserver')

from django.test.client import Client
from django.contrib.auth import get_user_model
from accounts.models import User, Subscription
from shops.models import Shop, Category

# リクエスト数をカウントするクラス
class RequestCounter:
    def __init__(self):
        self.reset()
    
    def reset(self):
        self.db_queries = 0
        self.http_requests = 0
        self.start_time = time.time()
    
    def get_stats(self):
        return {
            'db_queries': self.db_queries,
            'http_requests': self.http_requests,
            'duration': time.time() - self.start_time
        }

def create_test_data():
    """テスト用データを作成"""
    print("テスト用データを作成中...")
    
    # 管理者ユーザー
    admin_user, created = User.objects.get_or_create(
        email='admin@nagoyameshi.com',
        defaults={
            'manager_flag': True,
        }
    )
    if created:
        admin_user.set_password('adminpass')
        admin_user.save()
    
    # 一般ユーザー作成
    for i in range(10):
        user, created = User.objects.get_or_create(
            email=f'user{i}@example.com',
            defaults={
                'manager_flag': False,
            }
        )
        if created:
            user.set_password('userpass')
            user.save()
        
        # 半数のユーザーにサブスクリプションを追加
        if i < 5:
            Subscription.objects.get_or_create(
                user=user,
                defaults={'is_active': True}
            )
    
    # カテゴリ作成
    for i in range(5):
        Category.objects.get_or_create(
            name=f'カテゴリ{i}'
        )
    
    # 店舗作成
    categories = Category.objects.all()
    users = User.objects.filter(manager_flag=False)[:5]  # 一般ユーザーを取得
    
    for i in range(20):
        user = users[i % len(users)] if users else User.objects.first()
        shop, created = Shop.objects.get_or_create(
            name=f'テスト店舗{i}',
            defaults={
                'address': f'名古屋市テスト区{i}',
                'seat_count': 20 + (i * 5),
                'phone_number': f'052-000-000{i:02d}',
                'user': user,
            }
        )
        
        # ショップにカテゴリを追加
        if created and categories:
            from shops.models import ShopCategory
            category = categories[i % len(categories)]
            ShopCategory.objects.get_or_create(
                shop=shop,
                category=category
            )
    
    print(f"テストデータ作成完了:")
    print(f"- ユーザー: {User.objects.count()}人")
    print(f"- サブスクリプション: {Subscription.objects.count()}件")
    print(f"- カテゴリ: {Category.objects.count()}件")
    print(f"- 店舗: {Shop.objects.count()}件")

def test_page_requests(client, admin_user):
    """各ページのリクエスト数を測定"""
    results = {}
    
    # force_loginを使用してログイン
    client.force_login(admin_user)
    
    test_pages = [
        ('管理者ダッシュボード', '/admin-panel/'),
        ('ユーザー管理', '/admin-panel/users/'),
        ('ユーザー検索', '/admin-panel/users/?search=user'),
        ('店舗管理', '/admin-panel/shops/'),
        ('店舗作成', '/admin-panel/shops/create/'),
        ('カテゴリ管理', '/admin-panel/categories/'),
        ('一般サイトホーム', '/'),
        ('店舗一覧', '/shops/'),
        ('店舗詳細', '/shops/1/') if Shop.objects.exists() else None,
    ]
    
    for page_name, url in test_pages:
        if url is None:
            continue
            
        print(f"\n=== {page_name} のテスト ===")
        
        # データベースクエリ数をカウント
        from django.db import connection, reset_queries
        
        # クエリログをリセット
        reset_queries()
        
        start_time = time.time()
        
        try:
            response = client.get(url)
            query_count = len(connection.queries)
            duration = time.time() - start_time
            
            results[page_name] = {
                'url': url,
                'status_code': response.status_code,
                'query_count': query_count,
                'duration': duration,
                'content_length': len(response.content) if hasattr(response, 'content') else 0
            }
            
            print(f"URL: {url}")
            print(f"ステータス: {response.status_code}")
            print(f"DBクエリ数: {query_count}")
            print(f"レスポンス時間: {duration:.3f}秒")
            print(f"コンテンツサイズ: {len(response.content) if hasattr(response, 'content') else 0} bytes")
            
            # クエリの詳細を表示（最初の5つのみ）
            if query_count > 0:
                print("主要なクエリ:")
                for i, query in enumerate(connection.queries[:5]):
                    print(f"  {i+1}. {query['sql'][:100]}...")
                if query_count > 5:
                    print(f"  ... (他に{query_count - 5}個のクエリ)")
            
        except Exception as e:
            print(f"エラー: {e}")
            results[page_name] = {
                'url': url,
                'error': str(e),
                'query_count': 0,
                'duration': 0
            }
    
    return results

def analyze_queries():
    """問題のあるクエリパターンを分析"""
    print("\n=== クエリパターン分析 ===")
    
    # N+1問題の検出
    from django.db import connection, reset_queries
    
    # 管理者ユーザーを取得
    admin_user = User.objects.get(email='admin@nagoyameshi.com')
    
    # ユーザー一覧ページのクエリを分析
    client = Client()
    client.force_login(admin_user)
    
    reset_queries()
    response = client.get('/admin-panel/users/')
    queries = connection.queries
    
    print(f"ユーザー一覧ページの詳細分析:")
    print(f"総クエリ数: {len(queries)}")
    
    # クエリをパターン別に分類
    query_patterns = defaultdict(int)
    for query in queries:
        sql = query['sql']
        if 'SELECT' in sql:
            if 'auth_user' in sql:
                query_patterns['user_queries'] += 1
            elif 'subscription' in sql:
                query_patterns['subscription_queries'] += 1
            elif 'django_session' in sql:
                query_patterns['session_queries'] += 1
            else:
                query_patterns['other_queries'] += 1
    
    print("クエリパターン別集計:")
    for pattern, count in query_patterns.items():
        print(f"  {pattern}: {count}回")
    
    # 重複クエリの検出
    sql_counts = defaultdict(int)
    for query in queries:
        sql_normalized = query['sql'].replace('"', "'")  # クォートを正規化
        sql_counts[sql_normalized] += 1
    
    duplicates = {sql: count for sql, count in sql_counts.items() if count > 1}
    if duplicates:
        print(f"\n重複クエリ検出 ({len(duplicates)}パターン):")
        for sql, count in list(duplicates.items())[:3]:  # 最初の3つのみ表示
            print(f"  {count}回実行: {sql[:100]}...")
    
    return queries

def generate_optimization_report(results):
    """最適化レポートを生成"""
    print("\n" + "="*60)
    print("リクエスト最適化レポート")
    print("="*60)
    
    # クエリ数の多いページを特定
    high_query_pages = []
    for page_name, data in results.items():
        if 'query_count' in data and data['query_count'] > 10:
            high_query_pages.append((page_name, data['query_count'], data['url']))
    
    if high_query_pages:
        print("\n【警告】クエリ数が多いページ (10回以上):")
        high_query_pages.sort(key=lambda x: x[1], reverse=True)
        for page_name, query_count, url in high_query_pages:
            print(f"  - {page_name}: {query_count}回 ({url})")
    
    # レスポンス時間の遅いページ
    slow_pages = []
    for page_name, data in results.items():
        if 'duration' in data and data['duration'] > 1.0:
            slow_pages.append((page_name, data['duration'], data['url']))
    
    if slow_pages:
        print("\n【警告】レスポンスが遅いページ (1秒以上):")
        slow_pages.sort(key=lambda x: x[1], reverse=True)
        for page_name, duration, url in slow_pages:
            print(f"  - {page_name}: {duration:.2f}秒 ({url})")
    
    # 最適化の推奨事項
    print("\n【推奨最適化事項】")
    print("1. データベースクエリの最適化:")
    print("   - select_related()でJOINクエリを活用")
    print("   - prefetch_related()でN+1問題を解決")
    print("   - 不要なフィールドの取得を避ける")
    
    print("\n2. キャッシュの活用:")
    print("   - 頻繁にアクセスされるデータのキャッシュ")
    print("   - テンプレートフラグメントキャッシュ")
    print("   - 静的ファイルの適切なキャッシュ設定")
    
    print("\n3. フロントエンド最適化:")
    print("   - 不要なJavaScriptライブラリの削除")
    print("   - CSS/JSの圧縮")
    print("   - 画像の最適化")
    
    print("\n4. Heroku固有の最適化:")
    print("   - 接続プールの設定")
    print("   - KeepAlive接続の活用")
    print("   - 不要なミドルウェアの削除")

def main():
    """メイン実行関数"""
    print("Herokuリクエスト数最適化テスト開始")
    print("="*50)
    
    # テストデータ作成
    create_test_data()
    
    # 管理者ユーザー取得
    try:
        admin_user = User.objects.get(email='admin@nagoyameshi.com')
    except User.DoesNotExist:
        print("管理者ユーザーが見つかりません。")
        return
    
    # クライアント作成
    client = Client()
    
    # 各ページのリクエスト数測定
    results = test_page_requests(client, admin_user)
    
    # クエリ分析
    analyze_queries()
    
    # 最適化レポート生成
    generate_optimization_report(results)
    
    print("\n" + "="*50)
    print("テスト完了")

if __name__ == '__main__':
    main()
