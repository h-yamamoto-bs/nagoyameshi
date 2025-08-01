# Generated by Django 5.2.4 on 2025-07-30 13:21

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('shops', '0003_image'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='History',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('date', models.DateField()),
                ('number_of_people', models.PositiveIntegerField()),
                ('shop', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='histories', to='shops.shop')),
                ('user', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='histories', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'db_table': 'histories',
            },
        ),
        migrations.CreateModel(
            name='Review',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('rating', models.PositiveIntegerField()),
                ('comment', models.TextField(blank=True, null=True)),
                ('shop', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='reviews', to='shops.shop')),
            ],
            options={
                'db_table': 'reviews',
            },
        ),
        migrations.CreateModel(
            name='Favorite',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('shop', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='favorites', to='shops.shop')),
                ('user', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='favorites', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'db_table': 'favorites',
                'unique_together': {('shop', 'user')},
            },
        ),
    ]
