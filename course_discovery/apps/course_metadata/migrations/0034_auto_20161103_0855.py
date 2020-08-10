from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('course_metadata', '0033_courserun_mobile_available'),
    ]

    operations = [
        migrations.AlterField(
            model_name='courserun',
            name='start',
            field=models.DateTimeField(blank=True, null=True, db_index=True),
        ),
    ]
