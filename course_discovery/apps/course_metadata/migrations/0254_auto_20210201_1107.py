# Generated by Django 2.2.16 on 2021-02-01 11:07

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('course_metadata', '0253_auto_20210119_0650'),
    ]

    operations = [
        migrations.AddField(
            model_name='courserun',
            name='featured',
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name='historicalcourserun',
            name='featured',
            field=models.BooleanField(default=False),
        ),
    ]