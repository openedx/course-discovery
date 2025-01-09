# Generated by Django 4.2.17 on 2025-01-01 10:10

from django.conf import settings
import django.core.validators
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('course_metadata', '0345_courserun_translation_languages_and_more'),
    ]

    operations = [
        migrations.CreateModel(
            name='ArchiveCoursesConfig',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('change_date', models.DateTimeField(auto_now_add=True, verbose_name='Change date')),
                ('enabled', models.BooleanField(default=False, verbose_name='Enabled')),
                ('csv_file', models.FileField(help_text='A csv file containing uuid of the courses to be archived', upload_to='', validators=[django.core.validators.FileExtensionValidator(allowed_extensions=['csv'])])),
                ('mangle_end_date', models.BooleanField(default=False)),
                ('mangle_title', models.BooleanField(default=False)),
                ('changed_by', models.ForeignKey(editable=False, null=True, on_delete=django.db.models.deletion.PROTECT, to=settings.AUTH_USER_MODEL, verbose_name='Changed by')),
            ],
            options={
                'ordering': ('-change_date',),
                'abstract': False,
            },
        ),
    ]
