# -*- coding: utf-8 -*-
# Generated by Django 1.11.3 on 2017-11-07 17:07


from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('course_metadata', '0065_program_total_hours_of_effort'),
    ]

    operations = [
        migrations.AddField(
            model_name='courserun',
            name='outcome_override',
            field=models.TextField(blank=True, default=None, help_text="'What You Will Learn' description for this particular course run. Leave this value blank to default to the parent course's Outcome attribute.", null=True),
        ),
    ]
