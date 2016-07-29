# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models
import django.db.models.deletion
import django_extensions.db.fields
import sortedm2m.fields


class Migration(migrations.Migration):

    dependencies = [
        ('course_metadata', '0010_auto_20160731_0226'),
    ]

    operations = [
        migrations.CreateModel(
            name='CorporateEndorsement',
            fields=[
                ('id', models.AutoField(serialize=False, auto_created=True, primary_key=True, verbose_name='ID')),
                ('created', django_extensions.db.fields.CreationDateTimeField(auto_now_add=True, verbose_name='created')),
                ('modified', django_extensions.db.fields.ModificationDateTimeField(auto_now=True, verbose_name='modified')),
                ('corporation_name', models.CharField(max_length=128)),
                ('statement', models.TextField()),
                ('image', models.ForeignKey(blank=True, null=True, to='course_metadata.Image')),
            ],
            options={
                'abstract': False,
                'get_latest_by': 'modified',
                'ordering': ('-modified', '-created'),
            },
        ),
        migrations.CreateModel(
            name='Endorsement',
            fields=[
                ('id', models.AutoField(serialize=False, auto_created=True, primary_key=True, verbose_name='ID')),
                ('created', django_extensions.db.fields.CreationDateTimeField(auto_now_add=True, verbose_name='created')),
                ('modified', django_extensions.db.fields.ModificationDateTimeField(auto_now=True, verbose_name='modified')),
                ('quote', models.TextField()),
                ('endorser', models.ForeignKey(to='course_metadata.Person')),
            ],
            options={
                'abstract': False,
                'get_latest_by': 'modified',
                'ordering': ('-modified', '-created'),
            },
        ),
        migrations.CreateModel(
            name='FAQ',
            fields=[
                ('id', models.AutoField(serialize=False, auto_created=True, primary_key=True, verbose_name='ID')),
                ('created', django_extensions.db.fields.CreationDateTimeField(auto_now_add=True, verbose_name='created')),
                ('modified', django_extensions.db.fields.ModificationDateTimeField(auto_now=True, verbose_name='modified')),
                ('question', models.TextField()),
                ('answer', models.TextField()),
            ],
            options={
                'verbose_name_plural': 'FAQs',
                'verbose_name': 'FAQ',
            },
        ),
        migrations.CreateModel(
            name='JobOutlookItem',
            fields=[
                ('id', models.AutoField(serialize=False, auto_created=True, primary_key=True, verbose_name='ID')),
                ('created', django_extensions.db.fields.CreationDateTimeField(auto_now_add=True, verbose_name='created')),
                ('modified', django_extensions.db.fields.ModificationDateTimeField(auto_now=True, verbose_name='modified')),
                ('value', models.CharField(max_length=255)),
            ],
            options={
                'abstract': False,
            },
        ),
        migrations.CreateModel(
            name='ProgramType',
            fields=[
                ('id', models.AutoField(serialize=False, auto_created=True, primary_key=True, verbose_name='ID')),
                ('created', django_extensions.db.fields.CreationDateTimeField(auto_now_add=True, verbose_name='created')),
                ('modified', django_extensions.db.fields.ModificationDateTimeField(auto_now=True, verbose_name='modified')),
                ('name', models.CharField(max_length=32, unique=True)),
            ],
            options={
                'abstract': False,
                'get_latest_by': 'modified',
                'ordering': ('-modified', '-created'),
            },
        ),
        migrations.CreateModel(
            name='SeatType',
            fields=[
                ('id', models.AutoField(serialize=False, auto_created=True, primary_key=True, verbose_name='ID')),
                ('created', django_extensions.db.fields.CreationDateTimeField(auto_now_add=True, verbose_name='created')),
                ('modified', django_extensions.db.fields.ModificationDateTimeField(auto_now=True, verbose_name='modified')),
                ('name', models.CharField(max_length=64, unique=True)),
                ('slug', django_extensions.db.fields.AutoSlugField(editable=False, blank=True, populate_from='name')),
            ],
            options={
                'abstract': False,
                'get_latest_by': 'modified',
                'ordering': ('-modified', '-created'),
            },
        ),
        migrations.RemoveField(
            model_name='program',
            name='image',
        ),
        migrations.RemoveField(
            model_name='program',
            name='organizations',
        ),
        migrations.AddField(
            model_name='historicalorganization',
            name='banner_image',
            field=models.ForeignKey(on_delete=django.db.models.deletion.DO_NOTHING, blank=True, db_constraint=False, null=True, to='course_metadata.Image', related_name='+'),
        ),
        migrations.AddField(
            model_name='organization',
            name='banner_image',
            field=models.ForeignKey(blank=True, null=True, to='course_metadata.Image', related_name='bannered_organizations'),
        ),
        migrations.AddField(
            model_name='program',
            name='authoring_organizations',
            field=sortedm2m.fields.SortedManyToManyField(to='course_metadata.Organization', help_text=None, blank=True, related_name='authored_programs'),
        ),
        migrations.AddField(
            model_name='program',
            name='banner_image_url',
            field=models.URLField(blank=True, help_text='Image used atop marketing pages', null=True),
        ),
        migrations.AddField(
            model_name='program',
            name='card_image_url',
            field=models.URLField(blank=True, help_text='Image used for discovery cards', null=True),
        ),
        migrations.AddField(
            model_name='program',
            name='courses',
            field=models.ManyToManyField(to='course_metadata.Course'),
        ),
        migrations.AddField(
            model_name='program',
            name='credit_backing_organizations',
            field=sortedm2m.fields.SortedManyToManyField(to='course_metadata.Organization', help_text=None, blank=True, related_name='credit_backed_programs'),
        ),
        migrations.AddField(
            model_name='program',
            name='excluded_course_runs',
            field=models.ManyToManyField(to='course_metadata.CourseRun'),
        ),
        migrations.AddField(
            model_name='program',
            name='expected_learning_items',
            field=sortedm2m.fields.SortedManyToManyField(to='course_metadata.ExpectedLearningItem', help_text=None, blank=True),
        ),
        migrations.AddField(
            model_name='program',
            name='max_hours_effort_per_week',
            field=models.PositiveSmallIntegerField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='program',
            name='min_hours_effort_per_week',
            field=models.PositiveSmallIntegerField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='program',
            name='overview',
            field=models.TextField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='program',
            name='video',
            field=models.ForeignKey(blank=True, null=True, to='course_metadata.Video', default=None),
        ),
        migrations.AddField(
            model_name='program',
            name='weeks_to_complete',
            field=models.PositiveSmallIntegerField(blank=True, null=True),
        ),
        migrations.AlterField(
            model_name='organization',
            name='logo_image',
            field=models.ForeignKey(blank=True, null=True, to='course_metadata.Image', related_name='logoed_organizations'),
        ),
        migrations.AddField(
            model_name='programtype',
            name='applicable_seat_types',
            field=models.ManyToManyField(to='course_metadata.SeatType', help_text='Seat types that qualify for completion of the program.'),
        ),
        migrations.AddField(
            model_name='corporateendorsement',
            name='individual_endorsements',
            field=sortedm2m.fields.SortedManyToManyField(to='course_metadata.Endorsement', help_text=None),
        ),
        migrations.AddField(
            model_name='program',
            name='corporate_endorsements',
            field=sortedm2m.fields.SortedManyToManyField(to='course_metadata.CorporateEndorsement', help_text=None, blank=True),
        ),
        migrations.AddField(
            model_name='program',
            name='faq',
            field=sortedm2m.fields.SortedManyToManyField(to='course_metadata.FAQ', help_text=None, blank=True),
        ),
        migrations.AddField(
            model_name='program',
            name='individual_endorsements',
            field=sortedm2m.fields.SortedManyToManyField(to='course_metadata.Endorsement', help_text=None, blank=True),
        ),
        migrations.AddField(
            model_name='program',
            name='job_outlook_items',
            field=sortedm2m.fields.SortedManyToManyField(to='course_metadata.JobOutlookItem', help_text=None, blank=True),
        ),
        migrations.AddField(
            model_name='program',
            name='type',
            field=models.ForeignKey(blank=True, null=True, to='course_metadata.ProgramType'),
        ),
    ]
