from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('course_metadata', '0025_remove_program_category'),
    ]

    operations = [
        migrations.AlterField(
            model_name='courserun',
            name='end',
            field=models.DateTimeField(null=True, db_index=True, blank=True),
        ),
        migrations.AlterField(
            model_name='courserun',
            name='enrollment_end',
            field=models.DateTimeField(null=True, db_index=True, blank=True),
        ),
        migrations.AlterField(
            model_name='historicalcourserun',
            name='end',
            field=models.DateTimeField(null=True, db_index=True, blank=True),
        ),
        migrations.AlterField(
            model_name='historicalcourserun',
            name='enrollment_end',
            field=models.DateTimeField(null=True, db_index=True, blank=True),
        ),
    ]
