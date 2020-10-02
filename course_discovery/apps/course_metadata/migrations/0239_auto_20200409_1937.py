# -*- coding: utf-8 -*-
# Generated by Django 1.11.29 on 2020-04-09 19:37


from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('course_metadata', '0238_auto_20200408_1952'),
    ]

    operations = [
        migrations.AlterField(
            model_name='historicalcourserun',
            name='history_user',
            field=models.ForeignKey(db_constraint=False, null=True, on_delete=models.deletion.SET_NULL, related_name='+', to=settings.AUTH_USER_MODEL),
        ),
    ]
