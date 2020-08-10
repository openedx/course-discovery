from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('course_metadata', '0014_auto_20160811_0436'),
    ]

    operations = [
        migrations.AlterField(
            model_name='program',
            name='excluded_course_runs',
            field=models.ManyToManyField(blank=True, null=True, to='course_metadata.CourseRun'),
        ),
    ]
