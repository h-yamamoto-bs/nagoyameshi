from django.db import models
from accounts.models import User

# 会社情報
class CompanyInfo(models.Model):
    name = models.CharField(max_length=200, verbose_name='会社名')
    postal_code = models.CharField(max_length=8, verbose_name='郵便番号', null=True, blank=True)
    address = models.CharField(max_length=500, verbose_name='住所', null=True, blank=True)
    phone = models.CharField(max_length=20, verbose_name='電話番号', null=True, blank=True)
    email = models.EmailField(verbose_name='メールアドレス', null=True, blank=True)
    description = models.TextField(verbose_name='会社説明', null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = '会社情報'
        verbose_name_plural = '会社情報'

    def __str__(self):
        return self.name
