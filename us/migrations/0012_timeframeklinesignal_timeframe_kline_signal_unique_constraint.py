# Generated by Django 4.2.4 on 2023-11-04 16:46

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('us', '0011_remove_timeframeklinesignal_timeframe_kline_signal_unique_constraint_and_more'),
    ]

    operations = [
        migrations.AddConstraint(
            model_name='timeframeklinesignal',
            constraint=models.UniqueConstraint(models.F('timeframe_kline'), models.F('signal_variables'), name='timeframe_kline_signal_unique_constraint'),
        ),
    ]
