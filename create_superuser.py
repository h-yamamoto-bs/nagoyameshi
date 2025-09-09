#!/usr/bin/env python
"""
本番環境用スーパーユーザー作成スクリプト
"""
import os
import django

# Django設定
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'nagoyameshi.settings')
django.setup()

from accounts.models import User

def create_superuser():
    """本番環境用スーパーユーザーを作成"""
    try:
        # 既存のスーパーユーザーをチェック
        if User.objects.filter(is_superuser=True).exists():
            print("✅ スーパーユーザーが既に存在します")
            superuser = User.objects.filter(is_superuser=True).first()
            print(f"📧 管理者メール: {superuser.email}")
            return
        
        # 新しいスーパーユーザーを作成
        superuser = User.objects.create_user(
            email="admin@nagoyameshi.com",
            password="admin123456",  # 本番環境では必ず変更
            name="管理者",
            is_staff=True,
            is_superuser=True,
            is_active=True
        )
        
        print("🎉 スーパーユーザーを作成しました！")
        print(f"📧 メールアドレス: {superuser.email}")
        print("🔑 パスワード: admin123456")
        print("⚠️  本番環境では必ずパスワードを変更してください")
        
    except Exception as e:
        print(f"❌ エラー: {e}")

if __name__ == "__main__":
    create_superuser()
