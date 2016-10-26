# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models
import django_extensions.db.fields
from django.conf import settings
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('publisher', '0013_create_enable_email_notifications_switch'),
    ]

    operations = [
        migrations.CreateModel(
            name='HistoricalUserRole',
            fields=[
                ('id', models.IntegerField(blank=True, db_index=True, auto_created=True, verbose_name='ID')),
                ('created', django_extensions.db.fields.CreationDateTimeField(auto_now_add=True, verbose_name='created')),
                ('modified', django_extensions.db.fields.ModificationDateTimeField(auto_now=True, verbose_name='modified')),
                ('role', models.CharField(max_length=63, choices=[('partner_coordinator', 'Partner Coordinator'), ('reviewer', 'Reviewer'), ('publisher', 'Publisher')], verbose_name='Role Type')),
                ('is_active', models.BooleanField(default=True)),
                ('history_id', models.AutoField(primary_key=True, serialize=False)),
                ('history_date', models.DateTimeField()),
                ('history_type', models.CharField(max_length=1, choices=[('+', 'Created'), ('~', 'Changed'), ('-', 'Deleted')])),
                ('history_user', models.ForeignKey(to=settings.AUTH_USER_MODEL, on_delete=django.db.models.deletion.SET_NULL, related_name='+', null=True)),
                ('user', models.ForeignKey(blank=True, db_constraint=False, on_delete=django.db.models.deletion.DO_NOTHING, to=settings.AUTH_USER_MODEL, related_name='+', null=True)),
            ],
            options={
                'ordering': ('-history_date', '-history_id'),
                'get_latest_by': 'history_date',
                'verbose_name': 'historical user role',
            },
        ),
        migrations.CreateModel(
            name='UserRole',
            fields=[
                ('id', models.AutoField(primary_key=True, serialize=False, auto_created=True, verbose_name='ID')),
                ('created', django_extensions.db.fields.CreationDateTimeField(auto_now_add=True, verbose_name='created')),
                ('modified', django_extensions.db.fields.ModificationDateTimeField(auto_now=True, verbose_name='modified')),
                ('role', models.CharField(max_length=63, choices=[('partner_coordinator', 'Partner Coordinator'), ('reviewer', 'Reviewer'), ('publisher', 'Publisher')], verbose_name='Role Type')),
                ('is_active', models.BooleanField(default=True)),
                ('user', models.ForeignKey(related_name='roles', to=settings.AUTH_USER_MODEL)),
            ],
        ),
        migrations.AddField(
            model_name='courserun',
            name='user_role',
            field=models.ManyToManyField(related_name='publisher_course_runs', blank=True, to='publisher.UserRole'),
        ),
        migrations.AlterUniqueTogether(
            name='userrole',
            unique_together=set([('user', 'role')]),
        ),
    ]
