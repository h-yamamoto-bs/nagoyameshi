#!/usr/bin/env python
import os
import sys
import django
from datetime import date, timedelta
import random

# Django設定の初期化
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'nagoyameshi.settings')
django.setup()

from accounts.models import User
from shops.models import Shop, Favorite

def create_favorite_data():
    """お気に入りテストデータを作成"""
    
    print("お気に入りテストデータを作成中...")
    
    # 既存のお気に入りデータを削除
    Favorite.objects.all().delete()
    print("既存のお気に入りデータを削除しました。")
    
    # ユーザーと店舗を取得
    users = list(User.objects.filter(manager_flag=False))  # 一般ユーザーのみ
    shops = list(Shop.objects.all())
    
    if not users:
        print("ユーザーデータが見つかりません。先にユーザーデータを作成してください。")
        return
    
    if not shops:
        print("店舗データが見つかりません。先に店舗データを作成してください。")
        return
    
    favorites_data = []
    
    # 各ユーザーがランダムに店舗をお気に入りに追加
    for user in users:
        # 1人のユーザーが2-8店舗をお気に入りに追加
        num_favorites = random.randint(2, min(8, len(shops)))
        favorite_shops = random.sample(shops, num_favorites)
        
        for shop in favorite_shops:
            favorite = Favorite(
                user=user,
                shop=shop
            )
            favorites_data.append(favorite)
    
    # バルクインサート
    if favorites_data:
        Favorite.objects.bulk_create(favorites_data, ignore_conflicts=True)
        print(f"{len(favorites_data)}件のお気に入りデータを作成しました。")
    else:
        print("お気に入りデータが作成されませんでした。")
    
    # 統計情報を表示
    total_favorites = Favorite.objects.count()
    print(f"総お気に入り数: {total_favorites}件")
    
    # ユーザー別お気に入り数を表示
    for user in users[:5]:  # 最初の5人のみ表示
        user_favorites = Favorite.objects.filter(user=user).count()
        print(f"  {user.email}: {user_favorites}件のお気に入り")

if __name__ == '__main__':
    create_favorite_data()
