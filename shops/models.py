from django.db import models
from accounts.models import User

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
    rating = models.PositiveIntegerField(null=False, blank=False)
    comment = models.TextField(null=True, blank=True)

    class Meta:
        db_table = 'reviews'

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
