# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('course_metadata', '0005_auto_20160324_1931'),
    ]

    operations = [
        migrations.RenameField(
            model_name='courserun',
            old_name='announcment',
            new_name='announcement',
        ),
        migrations.RenameField(
            model_name='courserun',
            old_name='enrollment_period_end',
            new_name='enrollment_end',
        ),
        migrations.RenameField(
            model_name='courserun',
            old_name='enrollment_period_start',
            new_name='enrollment_start',
        ),
        migrations.RemoveField(
            model_name='course',
            name='name',
        ),
        migrations.RemoveField(
            model_name='prerequisite',
            name='courses',
        ),
        migrations.RemoveField(
            model_name='subject',
            name='course',
        ),
        migrations.AddField(
            model_name='course',
            name='prerequisites',
            field=models.ManyToManyField(to='course_metadata.Prerequisite'),
        ),
        migrations.AddField(
            model_name='course',
            name='subjects',
            field=models.ManyToManyField(to='course_metadata.Subject'),
        ),
        migrations.AlterField(
            model_name='courserunperson',
            name='relation_type',
            field=models.CharField(choices=[('instructor', 'Instructor'), ('staff', 'Staff')], max_length=63),
        ),
        migrations.AlterField(
            model_name='effort',
            name='max',
            field=models.PositiveSmallIntegerField(help_text='The maximum bound of expected effort in hours per week. For 6-10 hours per week, the `max` is 10.'),
        ),
        migrations.AlterField(
            model_name='effort',
            name='min',
            field=models.PositiveSmallIntegerField(help_text='The minimum bound of expected effort in hours per week. For 6-10 hours per week, the `min` is 6.'),
        ),
        migrations.AlterField(
            model_name='person',
            name='bio',
            field=models.TextField(null=True),
        ),
        migrations.AlterField(
            model_name='seat',
            name='price',
            field=models.DecimalField(max_digits=10, decimal_places=2),
        ),
        migrations.AlterField(
            model_name='seat',
            name='type',
            field=models.CharField(choices=[('honor', 'Honor'), ('audit', 'Audit'), ('verified', 'Verified'), ('professional', 'Professional'), ('credit', 'Credit')], max_length=63),
        ),
    ]
