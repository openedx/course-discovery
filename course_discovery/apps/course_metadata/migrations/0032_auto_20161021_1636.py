from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('course_metadata', '0031_courserun_weeks_to_complete'),
    ]

    operations = [
        migrations.AlterField(
            model_name='courserun',
            name='weeks_to_complete',
            field=models.PositiveSmallIntegerField(help_text='Estimated number of weeks needed to complete this course run.', blank=True, null=True),
        ),
        migrations.AlterField(
            model_name='program',
            name='weeks_to_complete',
            field=models.PositiveSmallIntegerField(help_text='This field is now deprecated (ECOM-6021).Estimated number of weeks needed to complete a course run belonging to this program.', blank=True, null=True),
        ),
    ]
