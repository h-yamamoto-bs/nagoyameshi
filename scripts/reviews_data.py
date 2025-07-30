#!/usr/bin/env python
import os
import sys
import django
from datetime import datetime, timedelta
import random
from django.utils import timezone

# Django設定の初期化
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'nagoyameshi.settings')
django.setup()

from accounts.models import User
from shops.models import Shop, Review

def create_review_data():
    """レビューテストデータを作成"""
    
    print("レビューテストデータを作成中...")
    
    # 既存のレビューデータを削除
    Review.objects.all().delete()
    print("既存のレビューデータを削除しました。")
    
    # ユーザーと店舗を取得
    users = list(User.objects.filter(manager_flag=False))  # 一般ユーザーのみ
    shops = list(Shop.objects.all())
    
    if not users:
        print("ユーザーデータが見つかりません。先にユーザーデータを作成してください。")
        return
    
    if not shops:
        print("店舗データが見つかりません。先に店舗データを作成してください。")
        return
    
    # レビューコメントのサンプル
    positive_comments = [
        "とても美味しかったです！雰囲気も良く、また来たいと思います。",
        "料理のクオリティが高く、スタッフの対応も素晴らしかったです。",
        "デートにおすすめの素敵なお店でした。特にデザートが絶品です。",
        "コストパフォーマンスが良く、満足度の高いお店です。",
        "新鮮な食材を使った料理が美味しく、大満足でした。",
        "落ち着いた雰囲気で、ゆっくりと食事を楽しめました。",
        "特別な日にぴったりのお店です。記念日に利用させていただきました。",
        "家族連れでも安心して利用できる温かいお店でした。"
    ]
    
    neutral_comments = [
        "普通のお店でした。可もなく不可もなくといった感じです。",
        "値段相応だと思います。特に印象に残ることはありませんでした。",
        "味は悪くないのですが、もう少し工夫があるとよいかもしれません。",
        "接客は良かったのですが、料理の提供時間が少し長かったです。",
        "立地は良いのですが、混雑していて少し騒がしかったです。"
    ]
    
    negative_comments = [
        "期待していたほどではありませんでした。改善を期待します。",
        "値段に対して料理の質が見合っていないように感じました。",
        "スタッフの対応が少し気になりました。",
        "予約時間に席が準備できておらず、待たされました。",
        "料理の味付けが濃すぎて、あまり好みではありませんでした。"
    ]
    
    reviews_data = []
    
    # 各ユーザーがランダムに店舗にレビューを投稿
    for user in users:
        # 1人のユーザーが2-8店舗にレビューを投稿
        num_reviews = random.randint(2, min(8, len(shops)))
        review_shops = random.sample(shops, num_reviews)
        
        for shop in review_shops:
            # 評価（1-5）
            rating = random.randint(1, 5)
            
            # 評価に応じてコメントを選択
            if rating >= 4:
                comment = random.choice(positive_comments)
            elif rating == 3:
                comment = random.choice(neutral_comments)
            else:
                comment = random.choice(negative_comments)
            
            # 5%の確率でコメントなし
            if random.random() < 0.05:
                comment = ""
            
            # 過去30日間のランダムな日時（タイムゾーン対応）
            days_ago = random.randint(0, 30)
            hours_ago = random.randint(0, 23)
            minutes_ago = random.randint(0, 59)
            created_time = timezone.now() - timedelta(days=days_ago, hours=hours_ago, minutes=minutes_ago)
            
            review = Review(
                user=user,
                shop=shop,
                rating=rating,
                comment=comment,
                created_at=created_time,
                updated_at=created_time
            )
            reviews_data.append(review)
    
    # バルクインサート
    if reviews_data:
        Review.objects.bulk_create(reviews_data, ignore_conflicts=True)
        print(f"{len(reviews_data)}件のレビューデータを作成しました。")
    else:
        print("レビューデータが作成されませんでした。")
    
    # 統計情報を表示
    total_reviews = Review.objects.count()
    print(f"総レビュー数: {total_reviews}件")
    
    # 評価別統計
    for rating in range(1, 6):
        count = Review.objects.filter(rating=rating).count()
        print(f"  {rating}つ星: {count}件")
    
    # 最新のレビューを表示
    recent_reviews = Review.objects.order_by('-created_at')[:5]
    print("最新のレビュー:")
    for review in recent_reviews:
        comment_preview = review.comment[:30] + "..." if len(review.comment) > 30 else review.comment
        print(f"  {review.rating}★ {review.shop.name} - {comment_preview}")

if __name__ == '__main__':
    create_review_data()
