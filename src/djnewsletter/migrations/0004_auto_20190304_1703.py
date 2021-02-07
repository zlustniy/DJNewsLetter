# Generated by Django 1.11.16 on 2019-03-04 17:03
import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ('djnewsletter', '0003_auto_20190304_1657'),
    ]

    operations = [
        migrations.AddField(
            model_name='emails',
            name='email_remote_id',
            field=models.CharField(blank=True, max_length=128, null=True),
        ),
        migrations.AddField(
            model_name='emails',
            name='used_server',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE,
                                    to='djnewsletter.EmailServers'),
        ),
    ]
