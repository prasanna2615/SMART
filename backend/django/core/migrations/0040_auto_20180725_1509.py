# -*- coding: utf-8 -*-
# Generated by Django 1.11.4 on 2018-07-25 15:09
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0039_data_upload_id"),
    ]

    operations = [
        migrations.AlterField(
            model_name="data",
            name="upload_id",
            field=models.CharField(max_length=100),
        ),
    ]
