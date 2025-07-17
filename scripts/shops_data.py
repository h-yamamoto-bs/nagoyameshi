from shops.models import Shop

def run():
    create()

def create():
    for i in range(21, 101):
        Shop.objects.create(
            name=f"Shop_{i}",
            address=f"Address_{i}",
            seat_count=10,
            user_id=1,
            phone_number="090-1234-5678",
        )