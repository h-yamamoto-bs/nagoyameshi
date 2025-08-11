from django.db import models
from accounts.models import User
from django.utils import timezone

# Create your models here.
class Shop(models.Model):
    name = models.CharField(max_length=100, null=False, blank=False)
    address = models.CharField(max_length=255, null=False, blank=False)
    seat_count = models.PositiveIntegerField(null=False, blank=False)
    phone_number = models.CharField(max_length=15, null=True, blank=True)
    user = models.ForeignKey(User, on_delete=models.CASCADE, null=False, blank=False)

    class Meta:
        db_table = 'shops'

    def __str__(self):
        return f"{self.name}（{self.address}）"

class Image(models.Model):
    shop = models.ForeignKey(Shop, related_name='images', on_delete=models.CASCADE)
    image = models.ImageField(upload_to='images/')

    class Meta:
        db_table = 'images'

    def __str__(self):
        return f"Image for {self.shop.name}"
    
class Review(models.Model):
    shop = models.ForeignKey(Shop, related_name='reviews', on_delete=models.CASCADE)
    user = models.ForeignKey(User, related_name='reviews', on_delete=models.CASCADE, null=True, blank=True)
    rating = models.PositiveIntegerField(choices=[(i, i) for i in range(1, 6)], null=False, blank=False)
    comment = models.TextField(max_length=1000, null=True, blank=True)
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'reviews'
        unique_together = ('shop', 'user')  # 1つの店舗に対してユーザーは1つのレビューのみ

    def __str__(self):
        user_email = self.user.email if self.user else "Unknown"
        return f'{user_email} - {self.shop.name} ({self.rating}★)'

class History(models.Model):
    shop = models.ForeignKey(Shop, related_name='histories', on_delete=models.CASCADE)
    user = models.ForeignKey(User, related_name='histories', on_delete=models.CASCADE)
    date = models.DateField(null=False, blank=False)
    number_of_people = models.PositiveIntegerField(null=False, blank=False)

    class Meta:
        db_table = 'histories'

class Favorite(models.Model):
    shop = models.ForeignKey(Shop, related_name='favorites', on_delete=models.CASCADE)
    user = models.ForeignKey(User, related_name='favorites', on_delete=models.CASCADE)

    class Meta:
        db_table = 'favorites'
        unique_together = ('shop', 'user')

    def __str__(self):
        return f"{self.user.email} - {self.shop.name}"

class category(models.Model):
    name = models.CharField(max_length=50, unique=True)

    class Meta:
        db_table = 'categories'

class ShopCategory(models.Model):
    shop = models.ForeignKey(Shop, related_name='categories', on_delete=models.CASCADE)
    category = models.ForeignKey(category, related_name='shop_categories', on_delete=models.CASCADE)

    class Meta:
        db_table = 'shop_categories'
        unique_together = ('shop', 'category')
