# Generated by Django 4.2.4 on 2024-02-29 11:12

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('us_orders', '0013_alter_order_previous_indicators'),
    ]

    operations = [
        migrations.AddField(
            model_name='order',
            name='note',
            field=models.TextField(blank=True, null=True),
        ),
    ]
