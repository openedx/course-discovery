# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models
import django_extensions.db.fields
import django.db.models.deletion
from django.conf import settings


class Migration(migrations.Migration):

    dependencies = [
        ('course_metadata', '0033_courserun_mobile_available'),
        ('auth', '0006_require_contenttypes_0002'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('publisher', '0014_auto_20161026_1625'),
    ]

    operations = [
        migrations.CreateModel(
            name='HistoricalOrganizationGroup',
            fields=[
                ('id', models.IntegerField(blank=True, db_index=True, verbose_name='ID', auto_created=True)),
                ('created', django_extensions.db.fields.CreationDateTimeField(verbose_name='created', auto_now_add=True)),
                ('modified', django_extensions.db.fields.ModificationDateTimeField(verbose_name='modified', auto_now=True)),
                ('history_id', models.AutoField(serialize=False, primary_key=True)),
                ('history_date', models.DateTimeField()),
                ('history_type', models.CharField(max_length=1, choices=[('+', 'Created'), ('~', 'Changed'), ('-', 'Deleted')])),
                ('group', models.ForeignKey(on_delete=django.db.models.deletion.DO_NOTHING, blank=True, db_constraint=False, to='auth.Group', null=True, related_name='+')),
                ('history_user', models.ForeignKey(on_delete=django.db.models.deletion.SET_NULL, to=settings.AUTH_USER_MODEL, null=True, related_name='+')),
                ('organization', models.ForeignKey(on_delete=django.db.models.deletion.DO_NOTHING, blank=True, db_constraint=False, to='course_metadata.Organization', null=True, related_name='+')),
            ],
            options={
                'get_latest_by': 'history_date',
                'verbose_name': 'historical organization group',
                'ordering': ('-history_date', '-history_id'),
            },
        ),
        migrations.CreateModel(
            name='OrganizationGroup',
            fields=[
                ('id', models.AutoField(serialize=False, primary_key=True, verbose_name='ID', auto_created=True)),
                ('created', django_extensions.db.fields.CreationDateTimeField(verbose_name='created', auto_now_add=True)),
                ('modified', django_extensions.db.fields.ModificationDateTimeField(verbose_name='modified', auto_now=True)),
                ('group', models.ForeignKey(to='auth.Group')),
                ('organization', models.ForeignKey(to='course_metadata.Organization')),
            ],
        ),
        migrations.AlterUniqueTogether(
            name='organizationgroup',
            unique_together=set([('organization', 'group')]),
        ),
    ]
