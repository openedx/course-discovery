# -*- coding: utf-8 -*-
# Generated by Django 1.11.21 on 2019-06-11 19:04
from __future__ import unicode_literals

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion
import django_extensions.db.fields
import simple_history.models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0013_historicalpartner'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('course_metadata', '0179_external-key'),
    ]

    operations = [
        migrations.CreateModel(
            name='HistoricalCourseEntitlement',
            fields=[
                ('id', models.IntegerField(auto_created=True, blank=True, db_index=True, verbose_name='ID')),
                ('created', django_extensions.db.fields.CreationDateTimeField(auto_now_add=True, verbose_name='created')),
                ('modified', django_extensions.db.fields.ModificationDateTimeField(auto_now=True, verbose_name='modified')),
                ('draft', models.BooleanField(default=False, help_text='Is this a draft version?')),
                ('price', models.DecimalField(decimal_places=2, default=0.0, max_digits=10)),
                ('sku', models.CharField(blank=True, max_length=128, null=True)),
                ('expires', models.DateTimeField(blank=True, null=True)),
                ('history_id', models.AutoField(primary_key=True, serialize=False)),
                ('history_date', models.DateTimeField()),
                ('history_change_reason', models.CharField(max_length=100, null=True)),
                ('history_type', models.CharField(choices=[('+', 'Created'), ('~', 'Changed'), ('-', 'Deleted')], max_length=1)),
                ('course', models.ForeignKey(blank=True, db_constraint=False, null=True, on_delete=django.db.models.deletion.DO_NOTHING, related_name='+', to='course_metadata.Course')),
                ('currency', models.ForeignKey(blank=True, db_constraint=False, default='USD', null=True, on_delete=django.db.models.deletion.DO_NOTHING, related_name='+', to='core.Currency')),
                ('draft_version', models.ForeignKey(blank=True, db_constraint=False, null=True, on_delete=django.db.models.deletion.DO_NOTHING, related_name='+', to='course_metadata.CourseEntitlement')),
                ('history_user', models.ForeignKey(null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='+', to=settings.AUTH_USER_MODEL)),
                ('mode', models.ForeignKey(blank=True, db_constraint=False, null=True, on_delete=django.db.models.deletion.DO_NOTHING, related_name='+', to='course_metadata.SeatType')),
                ('partner', models.ForeignKey(blank=True, db_constraint=False, null=True, on_delete=django.db.models.deletion.DO_NOTHING, related_name='+', to='core.Partner')),
            ],
            options={
                'verbose_name': 'historical course entitlement',
                'get_latest_by': 'history_date',
                'ordering': ('-history_date', '-history_id'),
            },
            bases=(simple_history.models.HistoricalChanges, models.Model),
        ),
        migrations.CreateModel(
            name='HistoricalSeat',
            fields=[
                ('id', models.IntegerField(auto_created=True, blank=True, db_index=True, verbose_name='ID')),
                ('created', django_extensions.db.fields.CreationDateTimeField(auto_now_add=True, verbose_name='created')),
                ('modified', django_extensions.db.fields.ModificationDateTimeField(auto_now=True, verbose_name='modified')),
                ('draft', models.BooleanField(default=False, help_text='Is this a draft version?')),
                ('type', models.CharField(choices=[('honor', 'Honor'), ('audit', 'Audit'), ('verified', 'Verified'), ('professional', 'Professional'), ('credit', 'Credit'), ('masters', 'Masters')], max_length=63)),
                ('price', models.DecimalField(decimal_places=2, default=0.0, max_digits=10)),
                ('upgrade_deadline', models.DateTimeField(blank=True, null=True)),
                ('credit_provider', models.CharField(blank=True, max_length=255, null=True)),
                ('credit_hours', models.IntegerField(blank=True, null=True)),
                ('sku', models.CharField(blank=True, max_length=128, null=True)),
                ('bulk_sku', models.CharField(blank=True, max_length=128, null=True)),
                ('history_id', models.AutoField(primary_key=True, serialize=False)),
                ('history_date', models.DateTimeField()),
                ('history_change_reason', models.CharField(max_length=100, null=True)),
                ('history_type', models.CharField(choices=[('+', 'Created'), ('~', 'Changed'), ('-', 'Deleted')], max_length=1)),
                ('course_run', models.ForeignKey(blank=True, db_constraint=False, null=True, on_delete=django.db.models.deletion.DO_NOTHING, related_name='+', to='course_metadata.CourseRun')),
                ('currency', models.ForeignKey(blank=True, db_constraint=False, null=True, on_delete=django.db.models.deletion.DO_NOTHING, related_name='+', to='core.Currency')),
                ('draft_version', models.ForeignKey(blank=True, db_constraint=False, null=True, on_delete=django.db.models.deletion.DO_NOTHING, related_name='+', to='course_metadata.Seat')),
                ('history_user', models.ForeignKey(null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='+', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'verbose_name': 'historical seat',
                'get_latest_by': 'history_date',
                'ordering': ('-history_date', '-history_id'),
            },
            bases=(simple_history.models.HistoricalChanges, models.Model),
        ),
    ]
