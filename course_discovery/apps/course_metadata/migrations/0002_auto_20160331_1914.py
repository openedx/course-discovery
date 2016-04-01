# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('course_metadata', '0001_initial'),
    ]

    operations = [
        migrations.AlterModelOptions(
            name='expectedlearningitem',
            options={},
        ),
        migrations.AlterModelOptions(
            name='syllabusitem',
            options={},
        ),
        migrations.AlterField(
            model_name='courserun',
            name='course',
            field=models.ForeignKey(related_name='course_runs', to='course_metadata.Course'),
        ),
        migrations.AlterField(
            model_name='expectedlearningitem',
            name='value',
            field=models.CharField(unique=True, max_length=255),
        ),
        migrations.AlterField(
            model_name='historicalseat',
            name='credit_hours',
            field=models.IntegerField(blank=True, null=True),
        ),
        migrations.AlterField(
            model_name='historicalseat',
            name='credit_provider',
            field=models.CharField(blank=True, max_length=255, null=True),
        ),
        migrations.AlterField(
            model_name='historicalseat',
            name='price',
            field=models.DecimalField(decimal_places=2, default=0.0, max_digits=10),
        ),
        migrations.AlterField(
            model_name='historicalseat',
            name='upgrade_deadline',
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AlterField(
            model_name='seat',
            name='credit_hours',
            field=models.IntegerField(blank=True, null=True),
        ),
        migrations.AlterField(
            model_name='seat',
            name='credit_provider',
            field=models.CharField(blank=True, max_length=255, null=True),
        ),
        migrations.AlterField(
            model_name='seat',
            name='price',
            field=models.DecimalField(decimal_places=2, default=0.0, max_digits=10),
        ),
        migrations.AlterField(
            model_name='seat',
            name='upgrade_deadline',
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AlterField(
            model_name='syllabusitem',
            name='value',
            field=models.CharField(unique=True, max_length=255),
        ),
    ]
