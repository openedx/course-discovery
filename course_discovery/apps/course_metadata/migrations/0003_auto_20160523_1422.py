from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('course_metadata', '0002_auto_20160406_1644'),
    ]

    operations = [
        migrations.AddField(
            model_name='courserun',
            name='marketing_url',
            field=models.URLField(max_length=255, blank=True, null=True),
        ),
        migrations.AddField(
            model_name='historicalcourserun',
            name='marketing_url',
            field=models.URLField(max_length=255, blank=True, null=True),
        ),
    ]
