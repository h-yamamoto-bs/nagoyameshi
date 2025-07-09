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