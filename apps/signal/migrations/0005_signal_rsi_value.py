# -*- coding: utf-8 -*-
# Generated by Django 1.11 on 2017-11-25 17:32
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('signal', '0004_auto_20171115_0627'),
    ]

    operations = [
        migrations.AddField(
            model_name='signal',
            name='rsi_value',
            field=models.FloatField(null=True),
        ),
    ]
