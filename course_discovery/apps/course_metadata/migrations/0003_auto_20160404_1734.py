# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('course_metadata', '0002_auto_20160404_1626'),
    ]

    operations = [
        migrations.AlterField(
            model_name='courserun',
            name='course',
            field=models.ForeignKey(related_name='course_runs', to='course_metadata.Course'),
        ),
        migrations.AlterField(
            model_name='historicalseat',
            name='credit_hours',
            field=models.IntegerField(null=True, blank=True),
        ),
        migrations.AlterField(
            model_name='historicalseat',
            name='credit_provider',
            field=models.CharField(max_length=255, null=True, blank=True),
        ),
        migrations.AlterField(
            model_name='historicalseat',
            name='price',
            field=models.DecimalField(decimal_places=2, default=0.0, max_digits=10),
        ),
        migrations.AlterField(
            model_name='historicalseat',
            name='upgrade_deadline',
            field=models.DateTimeField(null=True, blank=True),
        ),
        migrations.AlterField(
            model_name='seat',
            name='credit_hours',
            field=models.IntegerField(null=True, blank=True),
        ),
        migrations.AlterField(
            model_name='seat',
            name='credit_provider',
            field=models.CharField(max_length=255, null=True, blank=True),
        ),
        migrations.AlterField(
            model_name='seat',
            name='price',
            field=models.DecimalField(decimal_places=2, default=0.0, max_digits=10),
        ),
        migrations.AlterField(
            model_name='seat',
            name='upgrade_deadline',
            field=models.DateTimeField(null=True, blank=True),
        ),
    ]
