# Generated by Django 4.2.4 on 2023-11-06 11:21

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('us_orders', '0008_remove_ordergroup_order_group_unique_constraint_and_more'),
    ]

    operations = [
        migrations.AlterField(
            model_name='ordergroup',
            name='side',
            field=models.CharField(choices=[('BUY', 'BUY'), ('SELL', 'SELL')], default='BUY', max_length=4),
        ),
    ]
