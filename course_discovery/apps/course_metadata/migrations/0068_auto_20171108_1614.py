# -*- coding: utf-8 -*-
# Generated by Django 1.11.3 on 2017-11-08 16:14


import django.db.models.deletion
import django_extensions.db.fields
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0007_auto_20171004_1133'),
        ('course_metadata', '0067_auto_20171108_1432'),
    ]

    operations = [
        migrations.CreateModel(
            name='CourseEntitlement',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created', django_extensions.db.fields.CreationDateTimeField(auto_now_add=True, verbose_name='created')),
                ('modified', django_extensions.db.fields.ModificationDateTimeField(auto_now=True, verbose_name='modified')),
                ('price', models.DecimalField(decimal_places=2, default=0.0, max_digits=10)),
                ('sku', models.CharField(blank=True, max_length=128, null=True)),
                ('course', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='entitlements', to='course_metadata.Course')),
                ('currency', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='core.Currency')),
                ('mode', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='course_metadata.SeatType')),
            ],
        ),
        migrations.AlterUniqueTogether(
            name='courseentitlement',
            unique_together=set([('course', 'mode')]),
        ),
    ]
