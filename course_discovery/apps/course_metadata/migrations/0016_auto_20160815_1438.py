from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('course_metadata', '0015_auto_20160813_2142'),
    ]

    operations = [
        migrations.AlterField(
            model_name='program',
            name='excluded_course_runs',
            field=models.ManyToManyField(blank=True, to='course_metadata.CourseRun'),
        ),
    ]
