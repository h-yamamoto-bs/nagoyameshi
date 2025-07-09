# 使用する設定ファイルの指定とDjangoのセットアップ
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'nagoyameshi.settings')
django.setup()

# サンプルデータの作成
from shops.models import Shop

num = 30
for i in range(num):
    Shop.objects.create(
        name=f"Shop {i+1}",
        address=f"Address {i+1}",
        seat_count=3 * i,
        user_id=1
    )