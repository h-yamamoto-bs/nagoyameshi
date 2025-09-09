#!/usr/bin/env python
"""
メインアプリ（shops）リクエスト数測定テスト
Herokuのリクエスト制限対策のため、一般ユーザー向け機能のリクエスト数を測定する
"""

import os
import sys
import django
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
from django.db import connection, reset_queries
from shops.models import Shop, Category, ShopCategory
from accounts.models import Subscription
import random
from datetime import datetime, timedelta

User = get_user_model()

def create_test_data():
    """テスト用データを作成"""
    print("メインアプリ用テストデータを作成中...")
    
    # 管理者ユーザー
    admin_user, created = User.objects.get_or_create(
        email='admin@nagoyameshi.com',
        defaults={
            'manager_flag': True,
            'is_staff': True,
            'is_superuser': True
        }
    )
    if created:
        admin_user.set_password('adminpass')
        admin_user.save()
    
    # 一般ユーザーを作成
    users = []
    for i in range(15):
        user, created = User.objects.get_or_create(
            email=f'customer{i}@example.com',
            defaults={
                'manager_flag': False,
                'job': f'職業{i}',
                'birth_year': 1980 + (i % 20)
            }
        )
        if created:
            user.set_password('password123')
            user.save()
        users.append(user)
        
        # 一部のユーザーにサブスクリプションを設定
        if i % 3 == 0:
            Subscription.objects.get_or_create(
                user=user,
                defaults={
                    'start_date': datetime.now().date(),
                    'end_date': datetime.now().date() + timedelta(days=30),
                    'is_active': True,
                    'stripe_id': f'sub_test_{i}',
                    'stripe_customer_id': f'cus_test_{i}',
                    'stripe_subscription_id': f'sub_stripe_{i}'
                }
            )
    
    # カテゴリを作成
    categories = []
    category_names = ['和食', '洋食', '中華', 'イタリアン', 'フレンチ', 'カフェ', 'ラーメン', '居酒屋', 'バー', 'ファストフード']
    for i, name in enumerate(category_names):
        category, created = Category.objects.get_or_create(
            name=name
        )
        categories.append(category)
    
    # 店舗ユーザーを作成
    shop_owners = []
    for i in range(8):
        owner, created = User.objects.get_or_create(
            email=f'owner{i}@example.com',
            defaults={
                'manager_flag': False,
                'job': '店舗経営者',
                'birth_year': 1970 + (i % 15)
            }
        )
        if created:
            owner.set_password('ownerpass')
            owner.save()
        shop_owners.append(owner)
    
    # 店舗を作成
    for i in range(25):
        owner = shop_owners[i % len(shop_owners)]
        shop, created = Shop.objects.get_or_create(
            name=f'レストラン{i}',
            defaults={
                'address': f'愛知県名古屋市{i}区テスト{i}-{i}-{i}',
                'seat_count': 20 + (i * 2),
                'phone_number': f'052-{1000+i:04d}-{i:04d}',
                'user': owner
            }
        )
        
        # 各店舗にランダムにカテゴリを割り当て
        if created:
            selected_categories = random.sample(categories, min(3, len(categories)))
            for category in selected_categories:
                ShopCategory.objects.get_or_create(
                    shop=shop,
                    category=category
                )
    
    print(f"メインアプリテストデータ作成完了:")
    print(f"- ユーザー: {User.objects.count()}人")
    print(f"- サブスクリプション: {Subscription.objects.count()}件") 
    print(f"- カテゴリ: {Category.objects.count()}件")
    print(f"- 店舗: {Shop.objects.count()}件")

def test_main_app_pages(client, regular_user, premium_user):
    """メインアプリの各ページのリクエスト数を測定"""
    results = {}
    
    test_pages = [
        # ログイン不要ページ
        ('ホームページ', '/', None),
        ('店舗一覧', '/shops/shop_list/', None),
        ('店舗詳細', '/shops/shop_1/', None),
        ('店舗検索', '/shops/search/', None),
        
        # アカウント関連（ログイン不要）
        ('会員登録', '/accounts/register/', None),
        ('ログイン', '/accounts/login/', None),
        
        # ログイン後ページ（一般ユーザー）
        ('マイページ', '/accounts/mypage/', regular_user),
        ('アカウント一覧', '/accounts/account_list/', regular_user),
        
        # 有料会員限定機能（プレミアムユーザー）
        ('レビュー一覧', '/shops/reviews/', premium_user),
        ('サブスクリプション更新', '/accounts/subscription/update/', premium_user),
    ]
    
    for page_name, url, user in test_pages:
        print(f"\n=== {page_name} のテスト ===")
        
        # ログインが必要な場合
        if user:
            client.force_login(user)
        else:
            client.logout()
        
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
                'content_length': len(response.content) if hasattr(response, 'content') else 0,
                'requires_login': user is not None
            }
            
            print(f"URL: {url}")
            print(f"ステータス: {response.status_code}")
            print(f"DBクエリ数: {query_count}")
            print(f"レスポンス時間: {duration:.3f}秒")
            print(f"コンテンツサイズ: {len(response.content) if hasattr(response, 'content') else 0} bytes")
            print(f"ログイン要否: {'必要' if user else '不要'}")
            
            # クエリの詳細を表示（最初の5つのみ）
            if query_count > 0:
                print("主要なクエリ:")
                for i, query in enumerate(connection.queries[:5]):
                    sql = query['sql'][:80].replace('\n', ' ')
                    print(f"  {i+1}. {sql}...")
                if query_count > 5:
                    print(f"  ... (他に{query_count - 5}個のクエリ)")
            
        except Exception as e:
            print(f"エラー: {e}")
            results[page_name] = {
                'url': url,
                'error': str(e),
                'query_count': 0,
                'duration': 0,
                'requires_login': user is not None
            }
    
    return results

def analyze_main_app_patterns():
    """メインアプリの問題のあるクエリパターンを分析"""
    print("\n=== メインアプリ クエリパターン分析 ===")
    
    # 一般ユーザーを取得
    user = User.objects.filter(manager_flag=False).first()
    
    # 店舗一覧ページのクエリを分析
    client = Client()
    client.force_login(user) if user else None
    
    reset_queries()
    try:
        response = client.get('/shops/shop_list/')
        queries = connection.queries
        
        print(f"店舗一覧ページの詳細分析:")
        print(f"総クエリ数: {len(queries)}")
        
        # クエリパターン別集計
        query_patterns = defaultdict(int)
        for query in queries:
            sql = query['sql'].upper()
            if 'SELECT' in sql and 'SHOPS' in sql:
                query_patterns['shop_queries'] += 1
            elif 'SELECT' in sql and 'CATEGORIES' in sql:
                query_patterns['category_queries'] += 1
            elif 'SELECT' in sql and 'AUTH_USER' in sql:
                query_patterns['user_queries'] += 1
            elif 'SELECT' in sql and 'SHOP_CATEGORIES' in sql:
                query_patterns['shop_category_queries'] += 1
            else:
                query_patterns['other_queries'] += 1
        
        print("クエリパターン別集計:")
        for pattern, count in query_patterns.items():
            print(f"  {pattern}: {count}回")
            
    except Exception as e:
        print(f"分析エラー: {e}")

def generate_main_app_optimization_report(results):
    """メインアプリ最適化レポートを生成"""
    print("\n" + "="*60)
    print("メインアプリ リクエスト最適化レポート")
    print("="*60)
    
    # 最もクエリ数が多いページ
    high_query_pages = [(name, data['query_count']) for name, data in results.items() 
                       if 'query_count' in data and data['query_count'] > 3]
    high_query_pages.sort(key=lambda x: x[1], reverse=True)
    
    print("\n【最適化優先度の高いページ】")
    for page_name, query_count in high_query_pages:
        print(f"- {page_name}: {query_count}クエリ")
    
    print("\n【推奨最適化事項】")
    print("1. N+1問題の解決:")
    print("   - 店舗一覧でselect_related('user')使用")
    print("   - カテゴリ情報のprefetch_related()使用")
    
    print("\n2. ページネーション最適化:")
    print("   - 大量データページでのページング実装")
    print("   - count()クエリの最適化")
    
    print("\n3. キャッシュ活用:")
    print("   - 人気店舗ランキングのキャッシュ")
    print("   - カテゴリ一覧のキャッシュ")
    print("   - テンプレートフラグメントキャッシュ")
    
    print("\n4. フロントエンド最適化:")
    print("   - 画像の遅延読み込み")
    print("   - CSS/JSの圧縮")
    print("   - 静的ファイルのCDN配信")
    
    print("\n5. データベース最適化:")
    print("   - よく検索されるフィールドへのインデックス追加")
    print("   - 不要なフィールドの除外（defer/only使用）")

def main():
    """メインテスト実行"""
    print("メインアプリ Herokuリクエスト数最適化テスト開始")
    print("="*50)
    
    # テストデータ作成
    create_test_data()
    
    # テストクライアント作成
    client = Client()
    
    # テスト用ユーザー取得
    regular_user = User.objects.filter(manager_flag=False, subscription__isnull=True).first()
    premium_user = User.objects.filter(manager_flag=False, subscription__is_active=True).first()
    
    if not regular_user:
        print("警告: 一般ユーザーが見つかりません")
        return
    
    # ページテスト実行
    results = test_main_app_pages(client, regular_user, premium_user)
    
    # クエリパターン分析
    analyze_main_app_patterns()
    
    # 最適化レポート生成
    generate_main_app_optimization_report(results)
    
    print("\n" + "="*50)
    print("メインアプリテスト完了")

if __name__ == '__main__':
    main()
