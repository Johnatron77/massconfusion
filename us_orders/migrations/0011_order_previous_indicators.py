# Generated by Django 4.2.4 on 2023-11-24 20:39

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('us', '0014_strategyvariables_remove_timeframegroup_active_and_more'),
        ('us_orders', '0010_alter_ordergroup_orders'),
    ]

    operations = [
        migrations.AddField(
            model_name='order',
            name='previous_indicators',
            field=models.ManyToManyField(related_name='previous_indicators', to='us.timeframeklinesignal'),
        ),
    ]
