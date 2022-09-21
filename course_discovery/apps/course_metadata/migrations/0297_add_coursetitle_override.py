from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('course_metadata', '0296_geotargetingdataloaderconfiguration'),
    ]

    operations = [
        migrations.AddField(
            model_name='course',
            name='course_title_override',
            field=models.CharField(max_length=20, verbose_name='Course override', help_text='This field allows for override the default course to program/programme or other term you need', blank=True),
        ),
        migrations.AddField(
            model_name='historicalcourse',
            name='course_title_override',
            field=models.CharField(max_length=20, verbose_name='Course override', help_text='This field allows for override the default course to program/programme or other term you need', blank=True),
        )
    ]