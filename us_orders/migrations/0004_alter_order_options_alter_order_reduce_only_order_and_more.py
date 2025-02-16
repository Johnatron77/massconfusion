# Generated by Django 4.2.4 on 2023-10-17 17:49

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('woo', '0003_wooalgoorder_and_more'),
        ('us_orders', '0003_order_delete_algoorder'),
    ]

    operations = [
        migrations.AlterModelOptions(
            name='order',
            options={'ordering': ['-created_at'], 'verbose_name_plural': 'Orders'},
        ),
        migrations.AlterField(
            model_name='order',
            name='reduce_only_order',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name='reduce_only_order', to='woo.wooalgoorder'),
        ),
        migrations.AddConstraint(
            model_name='order',
            constraint=models.UniqueConstraint(fields=('order', 'reduce_only_order', 'indicator'), name='order_unique_constraint'),
        ),
    ]
