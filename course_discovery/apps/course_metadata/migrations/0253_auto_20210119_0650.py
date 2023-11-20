# Generated by Django 2.2.16 on 2021-01-19 06:50

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('course_metadata', '0252_add_honor_course_type'),
    ]

    operations = [
        migrations.AddField(
            model_name='historicalcourserun',
            name='invite_only',
            field=models.BooleanField(default=False),
        ),
        migrations.AlterField(
            model_name='leveltypetranslation',
            name='name_t',
            field=models.CharField(max_length=255, verbose_name='name'),
        ),
    ]