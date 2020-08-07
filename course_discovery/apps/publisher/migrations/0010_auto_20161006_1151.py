import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('publisher', '0009_auto_20160929_1927'),
    ]

    operations = [
        migrations.AlterField(
            model_name='course',
            name='expected_learnings',
            field=models.TextField(default=None, null=True, blank=True, verbose_name='Expected Learnings'),
        ),
        migrations.AlterField(
            model_name='course',
            name='full_description',
            field=models.TextField(default=None, null=True, blank=True, verbose_name='Full Description'),
        ),
        migrations.AlterField(
            model_name='course',
            name='level_type',
            field=models.ForeignKey(related_name='publisher_courses', default=None, to='course_metadata.LevelType', blank=True, verbose_name='Level Type', null=True, on_delete=django.db.models.deletion.CASCADE),
        ),
        migrations.AlterField(
            model_name='course',
            name='prerequisites',
            field=models.TextField(default=None, null=True, blank=True, verbose_name='Prerequisites'),
        ),
        migrations.AlterField(
            model_name='course',
            name='short_description',
            field=models.CharField(default=None, max_length=255, null=True, blank=True, verbose_name='Brief Description'),
        ),
        migrations.AlterField(
            model_name='courserun',
            name='language',
            field=models.ForeignKey(related_name='publisher_course_runs', to='ietf_language_tags.LanguageTag', verbose_name='Content Language', blank=True, null=True, on_delete=django.db.models.deletion.CASCADE),
        ),
        migrations.AlterField(
            model_name='historicalcourse',
            name='expected_learnings',
            field=models.TextField(default=None, null=True, blank=True, verbose_name='Expected Learnings'),
        ),
        migrations.AlterField(
            model_name='historicalcourse',
            name='full_description',
            field=models.TextField(default=None, null=True, blank=True, verbose_name='Full Description'),
        ),
        migrations.AlterField(
            model_name='historicalcourse',
            name='prerequisites',
            field=models.TextField(default=None, null=True, blank=True, verbose_name='Prerequisites'),
        ),
        migrations.AlterField(
            model_name='historicalcourse',
            name='short_description',
            field=models.CharField(default=None, max_length=255, null=True, blank=True, verbose_name='Brief Description'),
        ),
    ]
