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
from shops.models import Shop, History

def create_history_data():
    """利用履歴テストデータを作成"""
    
    print("利用履歴テストデータを作成中...")
    
    # 既存の履歴データを削除
    History.objects.all().delete()
    print("既存の履歴データを削除しました。")
    
    # ユーザーと店舗を取得
    users = list(User.objects.filter(manager_flag=False))  # 一般ユーザーのみ
    shops = list(Shop.objects.all())
    
    if not users:
        print("ユーザーデータが見つかりません。先にユーザーデータを作成してください。")
        return
    
    if not shops:
        print("店舗データが見つかりません。先に店舗データを作成してください。")
        return
    
    histories_data = []
    
    # 過去1年間の日付範囲を生成
    end_date = date.today()
    start_date = end_date - timedelta(days=365)
    
    # 各ユーザーの利用履歴を作成
    for user in users:
        # 1人のユーザーが5-20回の利用履歴
        num_visits = random.randint(5, 20)
        
        for _ in range(num_visits):
            # ランダムな店舗を選択
            shop = random.choice(shops)
            
            # ランダムな日付を生成（過去1年間）
            random_days = random.randint(0, 365)
            visit_date = start_date + timedelta(days=random_days)
            
            # 人数は1-8人
            number_of_people = random.randint(1, 8)
            
            history = History(
                user=user,
                shop=shop,
                date=visit_date,
                number_of_people=number_of_people
            )
            histories_data.append(history)
    
    # バルクインサート
    if histories_data:
        History.objects.bulk_create(histories_data)
        print(f"{len(histories_data)}件の利用履歴データを作成しました。")
    else:
        print("利用履歴データが作成されませんでした。")
    
    # 統計情報を表示
    total_histories = History.objects.count()
    print(f"総利用履歴数: {total_histories}件")
    
    # 最近の利用履歴を表示
    recent_histories = History.objects.order_by('-date')[:5]
    print("最近の利用履歴:")
    for history in recent_histories:
        print(f"  {history.date}: {history.user.email} が {history.shop.name} を {history.number_of_people}名で利用")
    
    # ユーザー別利用回数を表示
    for user in users[:5]:  # 最初の5人のみ表示
        user_histories = History.objects.filter(user=user).count()
        print(f"  {user.email}: {user_histories}回の利用")

if __name__ == '__main__':
    create_history_data()
