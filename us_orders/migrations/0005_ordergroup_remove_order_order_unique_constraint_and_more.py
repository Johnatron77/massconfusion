# Generated by Django 4.2.4 on 2023-10-18 16:46

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('us', '0007_timeframegroup_max_consecutive_and_more'),
        ('woo', '0004_wooalgoorder_created_at_wooalgoorder_realized_pnl_and_more'),
        ('us_orders', '0004_alter_order_options_alter_order_reduce_only_order_and_more'),
    ]

    operations = [
        migrations.CreateModel(
            name='OrderGroup',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
            ],
            options={
                'verbose_name_plural': 'Order Groups',
                'ordering': ['-created_at'],
            },
        ),
        migrations.RemoveConstraint(
            model_name='order',
            name='order_unique_constraint',
        ),
        migrations.RemoveField(
            model_name='order',
            name='reduce_only_order',
        ),
        migrations.AddField(
            model_name='order',
            name='stop',
            field=models.OneToOneField(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name='order_stop', to='woo.wooalgoorder'),
        ),
        migrations.AlterField(
            model_name='order',
            name='order',
            field=models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, to='woo.wooalgoorder'),
        ),
        migrations.AddConstraint(
            model_name='order',
            constraint=models.UniqueConstraint(fields=('order', 'stop', 'indicator'), name='order_unique_constraint'),
        ),
        migrations.AddField(
            model_name='ordergroup',
            name='group',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='us.timeframegroup'),
        ),
        migrations.AddField(
            model_name='ordergroup',
            name='orders',
            field=models.ManyToManyField(to='us_orders.order'),
        ),
        migrations.AddField(
            model_name='ordergroup',
            name='stop',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name='order_group_stop', to='woo.wooalgoorder'),
        ),
        migrations.AddConstraint(
            model_name='ordergroup',
            constraint=models.UniqueConstraint(fields=('group', 'stop'), name='order_group_unique_constraint'),
        ),
    ]
