import django.db.models.deletion
import sortedm2m.fields
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('publisher', '0001_initial'),
    ]

    operations = [
        migrations.AlterField(
            model_name='course',
            name='expected_learnings',
            field=models.TextField(verbose_name="What you'll learn", default=None, blank=True, null=True),
        ),
        migrations.AlterField(
            model_name='course',
            name='full_description',
            field=models.TextField(verbose_name='About this course', default=None, blank=True, null=True),
        ),
        migrations.AlterField(
            model_name='course',
            name='level_type',
            field=models.ForeignKey(blank=True, to='course_metadata.LevelType', verbose_name='Course level', default=None, null=True, related_name='publisher_courses', on_delete=django.db.models.deletion.CASCADE),
        ),
        migrations.AlterField(
            model_name='course',
            name='number',
            field=models.CharField(verbose_name='Course number', max_length=50, blank=True, null=True),
        ),
        migrations.AlterField(
            model_name='course',
            name='organizations',
            field=models.ManyToManyField(verbose_name='Partner Name', related_name='publisher_courses', blank=True, to='course_metadata.Organization', null=True),
        ),
        migrations.AlterField(
            model_name='course',
            name='primary_subject',
            field=models.ForeignKey(blank=True, to='course_metadata.Subject', null=True, default=None, related_name='publisher_courses_primary', on_delete=django.db.models.deletion.CASCADE),
        ),
        migrations.AlterField(
            model_name='course',
            name='secondary_subject',
            field=models.ForeignKey(blank=True, to='course_metadata.Subject', null=True, default=None, related_name='publisher_courses_secondary', on_delete=django.db.models.deletion.CASCADE),
        ),
        migrations.AlterField(
            model_name='course',
            name='short_description',
            field=models.CharField(verbose_name='Course subtitle', default=None, max_length=255, blank=True, null=True),
        ),
        migrations.AlterField(
            model_name='course',
            name='tertiary_subject',
            field=models.ForeignKey(blank=True, to='course_metadata.Subject', null=True, default=None, related_name='publisher_courses_tertiary', on_delete=django.db.models.deletion.CASCADE),
        ),
        migrations.AlterField(
            model_name='course',
            name='title',
            field=models.CharField(verbose_name='Course title', default=None, max_length=255, blank=True, null=True),
        ),
        migrations.AlterField(
            model_name='courserun',
            name='micromasters_name',
            field=models.CharField(null=True, blank=True, max_length=255),
        ),
        migrations.AlterField(
            model_name='courserun',
            name='staff',
            field=sortedm2m.fields.SortedManyToManyField(null=True, related_name='publisher_course_runs_staffed', blank=True, to='course_metadata.Person', help_text=None),
        ),
        migrations.AlterField(
            model_name='courserun',
            name='xseries_name',
            field=models.CharField(null=True, blank=True, max_length=255),
        ),
        migrations.AlterField(
            model_name='historicalcourse',
            name='expected_learnings',
            field=models.TextField(verbose_name="What you'll learn", default=None, blank=True, null=True),
        ),
        migrations.AlterField(
            model_name='historicalcourse',
            name='full_description',
            field=models.TextField(verbose_name='About this course', default=None, blank=True, null=True),
        ),
        migrations.AlterField(
            model_name='historicalcourse',
            name='number',
            field=models.CharField(verbose_name='Course number', max_length=50, blank=True, null=True),
        ),
        migrations.AlterField(
            model_name='historicalcourse',
            name='short_description',
            field=models.CharField(verbose_name='Course subtitle', default=None, max_length=255, blank=True, null=True),
        ),
        migrations.AlterField(
            model_name='historicalcourse',
            name='title',
            field=models.CharField(verbose_name='Course title', default=None, max_length=255, blank=True, null=True),
        ),
        migrations.AlterField(
            model_name='historicalcourserun',
            name='micromasters_name',
            field=models.CharField(null=True, blank=True, max_length=255),
        ),
        migrations.AlterField(
            model_name='historicalcourserun',
            name='xseries_name',
            field=models.CharField(null=True, blank=True, max_length=255),
        ),
        migrations.AlterField(
            model_name='historicalseat',
            name='type',
            field=models.CharField(choices=[('honor', 'Honor'), ('audit', 'Audit'), ('verified', 'Verified'), ('professional', 'Professional (with ID verification)'), ('no-id-professional', 'Professional (no ID verifiation)'), ('credit', 'Credit')], verbose_name='Seat type', max_length=63),
        ),
        migrations.AlterField(
            model_name='seat',
            name='currency',
            field=models.ForeignKey(to='core.Currency', related_name='publisher_seats', default='USD', on_delete=django.db.models.deletion.CASCADE),
        ),
        migrations.AlterField(
            model_name='seat',
            name='type',
            field=models.CharField(choices=[('honor', 'Honor'), ('audit', 'Audit'), ('verified', 'Verified'), ('professional', 'Professional (with ID verification)'), ('no-id-professional', 'Professional (no ID verifiation)'), ('credit', 'Credit')], verbose_name='Seat type', max_length=63),
        ),
    ]
