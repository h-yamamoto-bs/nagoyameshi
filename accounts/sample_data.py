# 使用する設定ファイルの指定とDjangoのセットアップ
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'nagoyameshi.settings')
django.setup()

# サンプルデータの作成
from accounts.models import User

num = 30
for i in range(num):
    User.objects.create(
        mail=f"user_{i+1}@example.com",
        password=f"password{i+1}"
    )