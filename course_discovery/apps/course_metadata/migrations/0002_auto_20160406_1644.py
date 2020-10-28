from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('course_metadata', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='course',
            name='marketing_url',
            field=models.URLField(null=True, max_length=255, blank=True),
        ),
        migrations.AddField(
            model_name='historicalcourse',
            name='marketing_url',
            field=models.URLField(null=True, max_length=255, blank=True),
        ),
    ]
