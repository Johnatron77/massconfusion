# Generated by Django 4.2.4 on 2023-11-04 15:16

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('woo', '0004_wooalgoorder_created_at_wooalgoorder_realized_pnl_and_more'),
    ]

    operations = [
        migrations.AddConstraint(
            model_name='wooalgoorder',
            constraint=models.CheckConstraint(check=models.Q(('side', 'SELL'), ('side', 'BUY'), _connector='OR'), name='woo_algo_order_type_is_sell_or_buy_constraint'),
        ),
    ]
