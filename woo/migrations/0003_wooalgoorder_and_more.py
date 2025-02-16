# Generated by Django 4.2.4 on 2023-10-17 16:44

from django.db import migrations, models
import time


class Migration(migrations.Migration):

    dependencies = [
        ('woo', '0002_alter_wooapierror_params'),
    ]

    operations = [
        migrations.CreateModel(
            name='WooAlgoOrder',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('order_id', models.IntegerField()),
                ('symbol', models.CharField(max_length=20)),
                ('type', models.CharField(default='MARKET', max_length=20)),
                ('algo_type', models.CharField(default='STOP', max_length=20)),
                ('side', models.CharField(max_length=4)),
                ('quantity', models.DecimalField(decimal_places=4, max_digits=20)),
                ('reduce_only', models.BooleanField(default=False)),
                ('is_triggered', models.BooleanField(default=False)),
                ('trigger_price', models.DecimalField(decimal_places=4, max_digits=20)),
                ('trigger_price_type', models.CharField(default='MARKET_PRICE', max_length=20)),
                ('trigger_trade_price', models.DecimalField(decimal_places=4, max_digits=20, null=True)),
                ('trigger_status', models.CharField(max_length=20, null=True)),
                ('trigger_time', models.DecimalField(decimal_places=4, max_digits=20, null=True)),
                ('status', models.CharField(max_length=20, null=True)),
                ('order_tag', models.CharField(max_length=20, null=True)),
                ('trade_id', models.IntegerField(null=True)),
                ('create_time', models.DecimalField(decimal_places=4, default=time.time, max_digits=20)),
                ('updated_time', models.DecimalField(decimal_places=4, default=time.time, max_digits=20)),
                ('total_executed_quantity', models.DecimalField(decimal_places=4, max_digits=20, null=True)),
                ('average_executed_price', models.DecimalField(decimal_places=4, max_digits=20, null=True)),
            ],
            options={
                'verbose_name_plural': 'Algo Orders',
            },
        ),
        migrations.AddConstraint(
            model_name='wooalgoorder',
            constraint=models.UniqueConstraint(fields=('order_id',), name='woo_algo_order_order_id_unique_constraint'),
        ),
    ]
