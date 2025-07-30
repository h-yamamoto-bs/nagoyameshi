#!/usr/bin/env python
import os
import sys
import django
import random

# Django設定の初期化
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'nagoyameshi.settings')
django.setup()

from accounts.models import User

def create_user_data():
    """テスト用ユーザーデータを作成"""
    
    print("テスト用ユーザーデータを作成中...")
    
    # 既存の一般ユーザー数を確認
    existing_users = User.objects.filter(manager_flag=False).count()
    print(f"既存の一般ユーザー数: {existing_users}件")
    
    # サンプルユーザー情報
    user_data = [
        {'email': 'user1@example.com', 'job': '会社員', 'birth_year': 1985},
        {'email': 'user2@example.com', 'job': 'エンジニア', 'birth_year': 1990},
        {'email': 'user3@example.com', 'job': 'デザイナー', 'birth_year': 1988},
        {'email': 'user4@example.com', 'job': '学生', 'birth_year': 2000},
        {'email': 'user5@example.com', 'job': '公務員', 'birth_year': 1982},
        {'email': 'user6@example.com', 'job': '主婦', 'birth_year': 1987},
        {'email': 'user7@example.com', 'job': '営業', 'birth_year': 1992},
        {'email': 'user8@example.com', 'job': '教師', 'birth_year': 1980},
        {'email': 'user9@example.com', 'job': 'フリーランス', 'birth_year': 1995},
        {'email': 'user10@example.com', 'job': '医師', 'birth_year': 1978},
        {'email': 'user11@example.com', 'job': '看護師', 'birth_year': 1989},
        {'email': 'user12@example.com', 'job': 'コンサルタント', 'birth_year': 1983},
        {'email': 'user13@example.com', 'job': '研究者', 'birth_year': 1986},
        {'email': 'user14@example.com', 'job': '自営業', 'birth_year': 1975},
        {'email': 'user15@example.com', 'job': 'アルバイト', 'birth_year': 1998},
    ]
    
    created_count = 0
    
    for data in user_data:
        # 既存のユーザーがいるかチェック
        if not User.objects.filter(email=data['email']).exists():
            user = User.objects.create_user(
                email=data['email'],
                password='testpass123',
                manager_flag=False,
                job=data['job'],
                birth_year=data['birth_year']
            )
            created_count += 1
            print(f"作成: {user.email} ({data['job']}, {data['birth_year']}年生)")
        else:
            print(f"スキップ: {data['email']} (既存)")
    
    print(f"\n{created_count}人の新しいユーザーを作成しました。")
    
    total_users = User.objects.filter(manager_flag=False).count()
    print(f"総一般ユーザー数: {total_users}人")

if __name__ == '__main__':
    create_user_data()
