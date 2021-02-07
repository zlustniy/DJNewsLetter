# Generated by Django 1.11.16 on 2019-03-20 11:24
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ('djnewsletter', '0004_auto_20190304_1703'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='emailservers',
            name='backend_name',
        ),
        migrations.AddField(
            model_name='emailservers',
            name='sending_method',
            field=models.CharField(choices=[('smtp', 'SMTP сервер'), ('unisender_api', 'UniSender API')],
                                   default='smtp', max_length=32, verbose_name='Способ отправки писем'),
        ),
    ]
