# Generated by Django 3.2.16 on 2022-10-21 17:45

from django.conf import settings
import django.core.validators
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('course_metadata', '0299_course_title_override'),
    ]

    operations = [
        migrations.AddField(
            model_name='geolocation',
            name='location_name',
            field=models.CharField(max_length=128, null=True),
        ),
        migrations.CreateModel(
            name='GeolocationDataLoaderConfiguration',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('change_date', models.DateTimeField(auto_now_add=True, verbose_name='Change date')),
                ('enabled', models.BooleanField(default=False, verbose_name='Enabled')),
                ('csv_file', models.FileField(help_text='It expects the data will be provided in a csv file format with first row containing all the headers.', upload_to='', validators=[django.core.validators.FileExtensionValidator(allowed_extensions=['csv'])])),
                ('changed_by', models.ForeignKey(editable=False, null=True, on_delete=django.db.models.deletion.PROTECT, to=settings.AUTH_USER_MODEL, verbose_name='Changed by')),
            ],
            options={
                'ordering': ('-change_date',),
                'abstract': False,
            },
        ),
    ]
