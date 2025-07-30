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

from accounts.models import User, Subscription

def create_subscription_data():
    """サブスクリプションテストデータを作成"""
    
    print("サブスクリプションテストデータを作成中...")
    
    # 既存のサブスクリプションデータを削除
    Subscription.objects.all().delete()
    print("既存のサブスクリプションデータを削除しました。")
    
    # 一般ユーザーを取得
    users = list(User.objects.filter(manager_flag=False))
    
    if not users:
        print("ユーザーデータが見つかりません。先にユーザーデータを作成してください。")
        return
    
    # 職業リスト
    jobs = [
        "会社員", "公務員", "自営業", "学生", "主婦/主夫", 
        "エンジニア", "デザイナー", "営業", "教師", "医師",
        "看護師", "弁護士", "会計士", "コンサルタント", "研究者",
        "フリーランス", "アルバイト", "無職", "退職者"
    ]
    
    # 生年（1950-2005年）
    birth_years = list(range(1950, 2006))
    
    subscriptions_data = []
    
    # ユーザーの約70%をサブスクリプション会員にする
    subscription_rate = int(len(users) * 0.7)
    subscription_users = random.sample(users, subscription_rate)
    
    for user in subscription_users:
        # 開始日（過去1年間のランダムな日付）
        days_ago = random.randint(0, 365)
        start_date = date.today() - timedelta(days=days_ago)
        
        # 80%の確率でアクティブ、20%で非アクティブ
        is_active = random.random() < 0.8
        
        # 非アクティブの場合は終了日を設定
        end_date = None
        if not is_active:
            # 開始日から1-300日後に終了
            end_days = random.randint(1, 300)
            end_date = start_date + timedelta(days=end_days)
            # 終了日が未来の場合は今日にする
            if end_date > date.today():
                end_date = date.today() - timedelta(days=random.randint(1, 30))
        
        # ランダムな職業と生年を設定
        job = random.choice(jobs)
        birth_year = random.choice(birth_years)
        
        subscription = Subscription(
            user=user,
            start_date=start_date,
            end_date=end_date,
            is_active=is_active,
            job=job,
            birth_year=birth_year
        )
        subscriptions_data.append(subscription)
    
    # バルクインサート
    if subscriptions_data:
        Subscription.objects.bulk_create(subscriptions_data)
        print(f"{len(subscriptions_data)}件のサブスクリプションデータを作成しました。")
    else:
        print("サブスクリプションデータが作成されませんでした。")
    
    # 統計情報を表示
    total_subscriptions = Subscription.objects.count()
    active_subscriptions = Subscription.objects.filter(is_active=True).count()
    inactive_subscriptions = total_subscriptions - active_subscriptions
    
    print(f"総サブスクリプション数: {total_subscriptions}件")
    print(f"  アクティブ: {active_subscriptions}件")
    print(f"  非アクティブ: {inactive_subscriptions}件")
    
    # 職業別統計（上位5つ）
    from django.db.models import Count
    job_stats = Subscription.objects.values('job').annotate(count=Count('job')).order_by('-count')[:5]
    print("職業別サブスクリプション数（上位5位）:")
    for stat in job_stats:
        print(f"  {stat['job']}: {stat['count']}件")
    
    # 年代別統計
    current_year = date.today().year
    age_groups = {
        "10代": 0, "20代": 0, "30代": 0, "40代": 0, 
        "50代": 0, "60代": 0, "70代以上": 0
    }
    
    for subscription in Subscription.objects.all():
        if subscription.birth_year:
            age = current_year - subscription.birth_year
            if age < 20:
                age_groups["10代"] += 1
            elif age < 30:
                age_groups["20代"] += 1
            elif age < 40:
                age_groups["30代"] += 1
            elif age < 50:
                age_groups["40代"] += 1
            elif age < 60:
                age_groups["50代"] += 1
            elif age < 70:
                age_groups["60代"] += 1
            else:
                age_groups["70代以上"] += 1
    
    print("年代別サブスクリプション数:")
    for age_group, count in age_groups.items():
        print(f"  {age_group}: {count}件")

if __name__ == '__main__':
    create_subscription_data()
