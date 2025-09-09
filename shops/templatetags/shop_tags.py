from django import template
from django.utils.safestring import mark_safe

register = template.Library()

@register.simple_tag
def main_image_url(shop):
    """
    店舗のメイン画像URLを効率的に取得
    prefetch_related('images')が適用されている場合、
    追加のDBクエリなしで画像を取得
    """
    if hasattr(shop, '_prefetched_objects_cache') and 'images' in shop._prefetched_objects_cache:
        # prefetch_relatedされている場合、キャッシュから取得
        images = list(shop._prefetched_objects_cache['images'])
        if images:
            return images[0].image.url
    else:
        # fallback: 従来通りの取得方法
        first_image = shop.images.first()
        if first_image:
            return first_image.image.url
    
    return '/static/images/no-image.jpg'  # デフォルト画像のパス

@register.simple_tag
def shop_categories(shop):
    """
    店舗のカテゴリ一覧を効率的に取得
    prefetch_related('categories__category')が適用されている場合、
    追加のDBクエリなしでカテゴリを取得
    """
    categories = []
    try:
        if hasattr(shop, '_prefetched_objects_cache') and 'categories' in shop._prefetched_objects_cache:
            # prefetch_relatedされている場合
            for shop_category in shop._prefetched_objects_cache['categories']:
                categories.append(shop_category.category)
        else:
            # fallback: 従来通りの取得方法
            for shop_category in shop.categories.all():
                categories.append(shop_category.category)
    except:
        pass
    
    return categories

@register.filter
def has_image(shop):
    """
    店舗が画像を持っているかチェック
    """
    if hasattr(shop, '_prefetched_objects_cache') and 'images' in shop._prefetched_objects_cache:
        return len(shop._prefetched_objects_cache['images']) > 0
    else:
        return shop.images.exists()
