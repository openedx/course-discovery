from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('course_metadata', '0027_auto_20160915_2038'),
    ]

    operations = [
        migrations.AddField(
            model_name='courserun',
            name='hidden',
            field=models.BooleanField(default=False),
        ),
    ]
