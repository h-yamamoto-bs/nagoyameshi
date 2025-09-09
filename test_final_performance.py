#!/usr/bin/env python
import os
import django
import time
import random
import string

# Djangoプロジェクトの設定を読み込み
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'nagoyameshi.settings')
django.setup()

from django.test import TestCase, Client
from django.db import connection
from django.contrib.auth import get_user_model
from shops.models import Shop, Category, Image, Review, Favorite, ShopCategory

class FinalOptimizationTest(TestCase):
    def setUp(self):
        """テスト用データの準備"""
        self.client = Client()
        
        # 既存の店舗を使用（新規作成ではなく）
        try:
            self.shop = Shop.objects.first()
            if not self.shop:
                raise Shop.DoesNotExist("店舗が見つかりません")
        except Shop.DoesNotExist:
            print("⚠️ 店舗データが存在しません。まずデータを追加してください。")
            return
        
        print(f"テストデータ確認:")
        print(f"  - 店舗: {self.shop.name}")
        print(f"  - レビュー: {Review.objects.filter(shop=self.shop).count()}件") 
        print(f"  - 画像: {Image.objects.filter(shop=self.shop).count()}件")

    def measure_queries(self, view_name, **kwargs):
        """指定されたビューのクエリ数を測定"""
        connection.queries_log.clear()
        
        start_time = time.time()
        response = self.client.get(view_name.format(**kwargs))
        end_time = time.time()
        
        query_count = len(connection.queries)
        response_time = (end_time - start_time) * 1000  # ms
        
        return {
            'query_count': query_count,
            'response_time': response_time,
            'status_code': response.status_code
        }

    def test_shop_detail_optimization(self):
        """店舗詳細ページの最適化テスト"""
        print("\n" + "="*60)
        print("店舗詳細ページ最適化テスト")
        print("="*60)
        
        result = self.measure_queries(f'/shops/shop_{self.shop.id}/')
        
        print(f"クエリ数: {result['query_count']}")
        print(f"レスポンス時間: {result['response_time']:.2f}ms")
        print(f"ステータスコード: {result['status_code']}")
        
        # 最適化目標: 5クエリ以下
        target_queries = 5
        if result['query_count'] <= target_queries:
            print(f"✅ 最適化成功！ 目標({target_queries}クエリ以下)を達成")
        else:
            print(f"⚠️ 最適化が必要。目標: {target_queries}クエリ、実際: {result['query_count']}クエリ")
        
        # 実際のクエリ内容を表示（デバッグ用）
        print("\n実行されたクエリ:")
        for i, query in enumerate(connection.queries, 1):
            print(f"{i:2d}. {query['sql'][:100]}...")
        
        return result

    def test_review_list_optimization(self):
        """レビュー一覧ページの最適化テスト"""
        print("\n" + "="*60)
        print("レビュー一覧ページ最適化テスト")
        print("="*60)
        
        result = self.measure_queries(f'/shops/shop_{self.shop.id}/reviews/')
        
        print(f"クエリ数: {result['query_count']}")
        print(f"レスポンス時間: {result['response_time']:.2f}ms")
        print(f"ステータスコード: {result['status_code']}")
        
        # 最適化目標: 8クエリ以下（ページネーション含む）
        target_queries = 8
        if result['query_count'] <= target_queries:
            print(f"✅ 最適化成功！ 目標({target_queries}クエリ以下)を達成")
        else:
            print(f"⚠️ 最適化が必要。目標: {target_queries}クエリ、実際: {result['query_count']}クエリ")
        
        # 実際のクエリ内容を表示（デバッグ用）
        print("\n実行されたクエリ:")
        for i, query in enumerate(connection.queries, 1):
            print(f"{i:2d}. {query['sql'][:100]}...")
        
        return result

    def test_overall_performance(self):
        """総合的なパフォーマンステスト"""
        print("\n" + "="*60)
        print("総合パフォーマンステスト結果")
        print("="*60)
        
        tests = {
            'shop_detail': self.test_shop_detail_optimization(),
            'review_list': self.test_review_list_optimization(),
        }
        
        total_queries = sum(test['query_count'] for test in tests.values())
        avg_response_time = sum(test['response_time'] for test in tests.values()) / len(tests)
        
        print(f"\n📊 総合結果:")
        print(f"  - 合計クエリ数: {total_queries}")
        print(f"  - 平均レスポンス時間: {avg_response_time:.2f}ms")
        
        # 全体的な最適化判定
        if total_queries <= 13:  # shop_detail(5) + review_list(8)
            print(f"🎉 全体的な最適化成功！")
        else:
            print(f"⚠️ 更なる最適化が必要")
        
        return tests


if __name__ == '__main__':
    # テストを実行
    from django.test.utils import get_runner
    from django.conf import settings
    
    test = FinalOptimizationTest()
    test.setUp()
    
    print("🚀 最終最適化テスト開始")
    print("⚡ パフォーマンス測定中...")
    
    results = test.test_overall_performance()
    
    print("\n" + "="*60)
    print("🎯 最適化目標達成状況")
    print("="*60)
    print("1. 店舗詳細ページ: 13クエリ → 5クエリ以下（目標）")
    print("2. レビュー一覧ページ: 999クエリ → 8クエリ以下（目標）")
    print("3. 全体的なレスポンス時間改善")
    print("="*60)
