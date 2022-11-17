# Generated by Django 3.2.15 on 2022-11-17 05:43

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('course_metadata', '0303_alter_degree_custom_program_duration'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='degree',
            name='custom_program_duration',
        ),
        migrations.AddField(
            model_name='degree',
            name='program_duration_override',
            field=models.CharField(blank=True, help_text='The custom program duration makes it possible to change the duration of the program, in months.', max_length=20, null=True),
        ),
    ]