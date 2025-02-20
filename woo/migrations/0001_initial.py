# Generated by Django 4.2.4 on 2023-08-31 16:42

from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
    ]

    operations = [
        migrations.CreateModel(
            name='WooAPIError',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('type', models.CharField(max_length=30)),
                ('url', models.CharField(max_length=100)),
                ('params', models.CharField(max_length=250)),
                ('error', models.CharField(max_length=400)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
            ],
        ),
    ]
