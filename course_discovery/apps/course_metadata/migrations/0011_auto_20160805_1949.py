import django.db.models.deletion
import django_extensions.db.fields
import djchoices.choices
import sortedm2m.fields
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('course_metadata', '0010_auto_20160731_0226'),
    ]

    operations = [
        migrations.CreateModel(
            name='CorporateEndorsement',
            fields=[
                ('id', models.AutoField(serialize=False, verbose_name='ID', auto_created=True, primary_key=True)),
                ('created', django_extensions.db.fields.CreationDateTimeField(verbose_name='created', auto_now_add=True)),
                ('modified', django_extensions.db.fields.ModificationDateTimeField(verbose_name='modified', auto_now=True)),
                ('corporation_name', models.CharField(max_length=128)),
                ('statement', models.TextField()),
                ('image', models.ForeignKey(blank=True, to='course_metadata.Image', null=True, on_delete=django.db.models.deletion.CASCADE)),
            ],
            options={
                'ordering': ('-modified', '-created'),
                'abstract': False,
                'get_latest_by': 'modified',
            },
        ),
        migrations.CreateModel(
            name='Endorsement',
            fields=[
                ('id', models.AutoField(serialize=False, verbose_name='ID', auto_created=True, primary_key=True)),
                ('created', django_extensions.db.fields.CreationDateTimeField(verbose_name='created', auto_now_add=True)),
                ('modified', django_extensions.db.fields.ModificationDateTimeField(verbose_name='modified', auto_now=True)),
                ('quote', models.TextField()),
                ('endorser', models.ForeignKey(to='course_metadata.Person', on_delete=django.db.models.deletion.CASCADE)),
            ],
            options={
                'ordering': ('-modified', '-created'),
                'abstract': False,
                'get_latest_by': 'modified',
            },
        ),
        migrations.CreateModel(
            name='FAQ',
            fields=[
                ('id', models.AutoField(serialize=False, verbose_name='ID', auto_created=True, primary_key=True)),
                ('created', django_extensions.db.fields.CreationDateTimeField(verbose_name='created', auto_now_add=True)),
                ('modified', django_extensions.db.fields.ModificationDateTimeField(verbose_name='modified', auto_now=True)),
                ('question', models.TextField()),
                ('answer', models.TextField()),
            ],
            options={
                'verbose_name': 'FAQ',
                'verbose_name_plural': 'FAQs',
            },
        ),
        migrations.CreateModel(
            name='JobOutlookItem',
            fields=[
                ('id', models.AutoField(serialize=False, verbose_name='ID', auto_created=True, primary_key=True)),
                ('created', django_extensions.db.fields.CreationDateTimeField(verbose_name='created', auto_now_add=True)),
                ('modified', django_extensions.db.fields.ModificationDateTimeField(verbose_name='modified', auto_now=True)),
                ('value', models.CharField(max_length=255)),
            ],
            options={
                'abstract': False,
            },
        ),
        migrations.CreateModel(
            name='ProgramType',
            fields=[
                ('id', models.AutoField(serialize=False, verbose_name='ID', auto_created=True, primary_key=True)),
                ('created', django_extensions.db.fields.CreationDateTimeField(verbose_name='created', auto_now_add=True)),
                ('modified', django_extensions.db.fields.ModificationDateTimeField(verbose_name='modified', auto_now=True)),
                ('name', models.CharField(max_length=32, unique=True)),
            ],
            options={
                'ordering': ('-modified', '-created'),
                'abstract': False,
                'get_latest_by': 'modified',
            },
        ),
        migrations.CreateModel(
            name='SeatType',
            fields=[
                ('id', models.AutoField(serialize=False, verbose_name='ID', auto_created=True, primary_key=True)),
                ('created', django_extensions.db.fields.CreationDateTimeField(verbose_name='created', auto_now_add=True)),
                ('modified', django_extensions.db.fields.ModificationDateTimeField(verbose_name='modified', auto_now=True)),
                ('name', models.CharField(max_length=64, unique=True)),
                ('slug', django_extensions.db.fields.AutoSlugField(editable=False, populate_from='name', blank=True)),
            ],
            options={
                'ordering': ('-modified', '-created'),
                'abstract': False,
                'get_latest_by': 'modified',
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
            field=models.ForeignKey(blank=True, related_name='+', on_delete=django.db.models.deletion.DO_NOTHING, db_constraint=False, to='course_metadata.Image', null=True),
        ),
        migrations.AddField(
            model_name='organization',
            name='banner_image',
            field=models.ForeignKey(blank=True, related_name='bannered_organizations', to='course_metadata.Image', null=True, on_delete=django.db.models.deletion.CASCADE),
        ),
        migrations.AddField(
            model_name='program',
            name='authoring_organizations',
            field=sortedm2m.fields.SortedManyToManyField(related_name='authored_programs', help_text=None, blank=True, to='course_metadata.Organization'),
        ),
        migrations.AddField(
            model_name='program',
            name='banner_image_url',
            field=models.URLField(help_text='Image used atop detail pages', blank=True, null=True),
        ),
        migrations.AddField(
            model_name='program',
            name='card_image_url',
            field=models.URLField(help_text='Image used for discovery cards', blank=True, null=True),
        ),
        migrations.AddField(
            model_name='program',
            name='courses',
            field=models.ManyToManyField(to='course_metadata.Course'),
        ),
        migrations.AddField(
            model_name='program',
            name='credit_backing_organizations',
            field=sortedm2m.fields.SortedManyToManyField(related_name='credit_backed_programs', help_text=None, blank=True, to='course_metadata.Organization'),
        ),
        migrations.AddField(
            model_name='program',
            name='excluded_course_runs',
            field=models.ManyToManyField(to='course_metadata.CourseRun'),
        ),
        migrations.AddField(
            model_name='program',
            name='expected_learning_items',
            field=sortedm2m.fields.SortedManyToManyField(help_text=None, blank=True, to='course_metadata.ExpectedLearningItem'),
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
            field=models.ForeignKey(default=None, blank=True, to='course_metadata.Video', null=True, on_delete=django.db.models.deletion.CASCADE),
        ),
        migrations.AddField(
            model_name='program',
            name='weeks_to_complete',
            field=models.PositiveSmallIntegerField(blank=True, null=True),
        ),
        migrations.AlterField(
            model_name='organization',
            name='logo_image',
            field=models.ForeignKey(blank=True, related_name='logoed_organizations', to='course_metadata.Image', null=True, on_delete=django.db.models.deletion.CASCADE),
        ),
        migrations.AlterField(
            model_name='program',
            name='status',
            field=models.CharField(choices=[('unpublished', 'Unpublished'), ('active', 'Active'), ('retired', 'Retired'), ('deleted', 'Deleted')], validators=[djchoices.choices.ChoicesValidator({'deleted': 'Deleted', 'retired': 'Retired', 'active': 'Active', 'unpublished': 'Unpublished'})], max_length=24, help_text='The lifecycle status of this Program.'),
        ),
        migrations.AddField(
            model_name='programtype',
            name='applicable_seat_types',
            field=models.ManyToManyField(to='course_metadata.SeatType', help_text='Seat types that qualify for completion of programs of this type. Learners completing associated courses, but enrolled in other seat types, will NOT have their completion of the course counted toward the completion of the program.'),
        ),
        migrations.AddField(
            model_name='corporateendorsement',
            name='individual_endorsements',
            field=sortedm2m.fields.SortedManyToManyField(to='course_metadata.Endorsement', help_text=None),
        ),
        migrations.AddField(
            model_name='program',
            name='corporate_endorsements',
            field=sortedm2m.fields.SortedManyToManyField(help_text=None, blank=True, to='course_metadata.CorporateEndorsement'),
        ),
        migrations.AddField(
            model_name='program',
            name='faq',
            field=sortedm2m.fields.SortedManyToManyField(help_text=None, blank=True, to='course_metadata.FAQ'),
        ),
        migrations.AddField(
            model_name='program',
            name='individual_endorsements',
            field=sortedm2m.fields.SortedManyToManyField(help_text=None, blank=True, to='course_metadata.Endorsement'),
        ),
        migrations.AddField(
            model_name='program',
            name='job_outlook_items',
            field=sortedm2m.fields.SortedManyToManyField(help_text=None, blank=True, to='course_metadata.JobOutlookItem'),
        ),
        migrations.AddField(
            model_name='program',
            name='type',
            field=models.ForeignKey(blank=True, to='course_metadata.ProgramType', null=True, on_delete=django.db.models.deletion.CASCADE),
        ),
    ]
