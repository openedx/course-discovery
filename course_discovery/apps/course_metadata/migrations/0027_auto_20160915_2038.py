from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('course_metadata', '0026_auto_20160912_2146'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='historicalcourse',
            name='history_user',
        ),
        migrations.RemoveField(
            model_name='historicalcourse',
            name='level_type',
        ),
        migrations.RemoveField(
            model_name='historicalcourse',
            name='partner',
        ),
        migrations.RemoveField(
            model_name='historicalcourse',
            name='video',
        ),
        migrations.RemoveField(
            model_name='historicalcourserun',
            name='course',
        ),
        migrations.RemoveField(
            model_name='historicalcourserun',
            name='history_user',
        ),
        migrations.RemoveField(
            model_name='historicalcourserun',
            name='language',
        ),
        migrations.RemoveField(
            model_name='historicalcourserun',
            name='syllabus',
        ),
        migrations.RemoveField(
            model_name='historicalcourserun',
            name='video',
        ),
        migrations.RemoveField(
            model_name='historicalorganization',
            name='history_user',
        ),
        migrations.RemoveField(
            model_name='historicalorganization',
            name='partner',
        ),
        migrations.RemoveField(
            model_name='historicalperson',
            name='history_user',
        ),
        migrations.RemoveField(
            model_name='historicalperson',
            name='partner',
        ),
        migrations.RemoveField(
            model_name='historicalseat',
            name='course_run',
        ),
        migrations.RemoveField(
            model_name='historicalseat',
            name='currency',
        ),
        migrations.RemoveField(
            model_name='historicalseat',
            name='history_user',
        ),
        migrations.DeleteModel(
            name='HistoricalCourse',
        ),
        migrations.DeleteModel(
            name='HistoricalCourseRun',
        ),
        migrations.DeleteModel(
            name='HistoricalOrganization',
        ),
        migrations.DeleteModel(
            name='HistoricalPerson',
        ),
        migrations.DeleteModel(
            name='HistoricalSeat',
        ),
    ]
