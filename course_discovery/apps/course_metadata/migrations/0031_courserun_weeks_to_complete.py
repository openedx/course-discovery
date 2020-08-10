from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('course_metadata', '0030_create_refresh_command_switches'),
    ]

    operations = [
        migrations.AddField(
            model_name='courserun',
            name='weeks_to_complete',
            field=models.PositiveSmallIntegerField(null=True, blank=True, help_text='This field is now deprecated (ECOM-6021).Estimated number of weeks needed to complete a course run.'),
        ),
    ]
