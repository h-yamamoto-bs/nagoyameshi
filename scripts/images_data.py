from shops.models import Image, Shop

def run():
    create()

def create():
    shop_ids = Shop.objects.values_list('id', flat=True)

    image_urls = [
        "images/dessert.jpg",
        "images/humans.jpg",
        "images/meal.jpg",
        "images/scenery.jpg",
        "images/seat.jpg"
    ]

    for id in shop_ids:
        for url in image_urls:
            Image.objects.create(
                image=url,
                shop_id=id
            )