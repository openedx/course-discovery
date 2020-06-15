# -*- coding: utf-8 -*-
# Generated by Django 1.11.15 on 2018-08-15 16:54


from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('course_metadata', '0099_micromasters_details'),
    ]

    operations = [
        migrations.AddField(
            model_name='degree',
            name='costs_fine_print',
            field=models.TextField(blank=True, help_text="The fine print that displays at the Tuition section's bottom", null=True),
        ),
        migrations.AddField(
            model_name='degree',
            name='deadlines_fine_print',
            field=models.TextField(blank=True, help_text="The fine print that displays at the Deadline section's bottom", null=True),
        ),
    ]
