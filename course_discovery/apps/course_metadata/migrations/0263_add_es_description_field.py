# Generated by Django 2.2.19 on 2021-03-24 06:32

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('course_metadata', '0262_update_course_metadata_app_models'),
    ]

    operations = [
        migrations.AddField(
            model_name='historicalorganization',
            name='description_es',
            field=models.TextField(blank=True, help_text='For seo, this field allows for alternate spanish description to be manually inputted', verbose_name='Spanish Description'),
        ),
        migrations.AddField(
            model_name='organization',
            name='description_es',
            field=models.TextField(blank=True, help_text='For seo, this field allows for alternate spanish description to be manually inputted', verbose_name='Spanish Description'),
        ),
    ]
