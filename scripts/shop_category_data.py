from shops.models import Shop, Category, ShopCategory
import random

def run():
    # 既存のShopCategoryデータをクリア（必要に応じてコメントアウト）
    print("既存のShopCategoryデータをクリアしています...")
    ShopCategory.objects.all().delete()
    print("クリア完了")
    
    create()

def input(category_ids, shop_id):
    random_id = random.choice(category_ids)

    # 重複チェック：既に存在する組み合わせは作成しない
    if not ShopCategory.objects.filter(category_id=random_id, shop_id=shop_id).exists():
        ShopCategory.objects.create(
            category_id=random_id,
            shop_id=shop_id
        )
        print(f"Shop {shop_id} にカテゴリ {random_id} を追加しました")
    else:
        print(f"Shop {shop_id} とカテゴリ {random_id} の組み合わせは既に存在します")


def create():
    shop_ids = Shop.objects.values_list('id', flat=True)
    category_ids = Category.objects.values_list('id', flat=True)

    for shop_id in shop_ids:
        input(category_ids, shop_id)

        next = random.choice([True, False])
        if next:
            input(category_ids, shop_id)
