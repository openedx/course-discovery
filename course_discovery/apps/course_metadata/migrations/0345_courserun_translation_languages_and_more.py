# Generated by Django 4.2.13 on 2024-08-28 04:13

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('course_metadata', '0344_courserun_fixed_price_usd_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='courserun',
            name='translation_languages',
            field=models.JSONField(blank=True, help_text='A JSON list detailing the available translations for this run. Each element in the list is a dictionary containing two keys: the language code and the language label. These entries represent the languages into which the run content can be translated.', null=True),
        ),
        migrations.AddField(
            model_name='historicalcourserun',
            name='translation_languages',
            field=models.JSONField(blank=True, help_text='A JSON list detailing the available translations for this run. Each element in the list is a dictionary containing two keys: the language code and the language label. These entries represent the languages into which the run content can be translated.', null=True),
        ),
    ]
