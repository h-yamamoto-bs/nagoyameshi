import os
import sys
import django

# Djangoプロジェクトのルートディレクトリをパスに追加
project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.append(project_root)

# Django設定を読み込み
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'nagoyameshi.settings')
django.setup()

from django.contrib.auth.models import User
from django.db import transaction

def create_sample_users():

    # 重複するユーザーがいなければ追加
    for i in range(1, 31):
        email = f'user{i}@example.com'
        password = 'password'

        if not User.objects.filter(email=email).exists():
            user = User.objects.create_user(
                email=email,
                password=password,
            )
            print(f'ID: {user.id} email: {user.mail} を作成しました。')