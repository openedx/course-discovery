import django.db.models.deletion
import django_extensions.db.fields
import sortedm2m.fields
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0005_populate_currencies'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('ietf_language_tags', '0002_language_tag_data_migration'),
    ]

    operations = [
        migrations.CreateModel(
            name='Course',
            fields=[
                ('id', models.AutoField(primary_key=True, auto_created=True, verbose_name='ID', serialize=False)),
                ('created', django_extensions.db.fields.CreationDateTimeField(auto_now_add=True, verbose_name='created')),
                ('modified', django_extensions.db.fields.ModificationDateTimeField(verbose_name='modified', auto_now=True)),
                ('key', models.CharField(db_index=True, max_length=255, unique=True)),
                ('title', models.CharField(default=None, blank=True, max_length=255, null=True)),
                ('short_description', models.CharField(default=None, blank=True, max_length=255, null=True)),
                ('full_description', models.TextField(default=None, blank=True, null=True)),
            ],
            options={
                'ordering': ('-modified', '-created'),
                'get_latest_by': 'modified',
                'abstract': False,
            },
        ),
        migrations.CreateModel(
            name='CourseOrganization',
            fields=[
                ('id', models.AutoField(primary_key=True, auto_created=True, verbose_name='ID', serialize=False)),
                ('created', django_extensions.db.fields.CreationDateTimeField(auto_now_add=True, verbose_name='created')),
                ('modified', django_extensions.db.fields.ModificationDateTimeField(verbose_name='modified', auto_now=True)),
                ('relation_type', models.CharField(max_length=63, choices=[('owner', 'Owner'), ('sponsor', 'Sponsor')])),
                ('course', models.ForeignKey(to='course_metadata.Course', on_delete=django.db.models.deletion.CASCADE)),
            ],
        ),
        migrations.CreateModel(
            name='CourseRun',
            fields=[
                ('id', models.AutoField(primary_key=True, auto_created=True, verbose_name='ID', serialize=False)),
                ('created', django_extensions.db.fields.CreationDateTimeField(auto_now_add=True, verbose_name='created')),
                ('modified', django_extensions.db.fields.ModificationDateTimeField(verbose_name='modified', auto_now=True)),
                ('key', models.CharField(max_length=255, unique=True)),
                ('title_override', models.CharField(default=None, blank=True, max_length=255, null=True, help_text="Title specific for this run of a course. Leave this value blank to default to the parent course's title.")),
                ('start', models.DateTimeField(blank=True, null=True)),
                ('end', models.DateTimeField(blank=True, null=True)),
                ('enrollment_start', models.DateTimeField(blank=True, null=True)),
                ('enrollment_end', models.DateTimeField(blank=True, null=True)),
                ('announcement', models.DateTimeField(blank=True, null=True)),
                ('short_description_override', models.CharField(default=None, blank=True, max_length=255, null=True, help_text="Short description specific for this run of a course. Leave this value blank to default to the parent course's short_description attribute.")),
                ('full_description_override', models.TextField(default=None, blank=True, help_text="Full description specific for this run of a course. Leave this value blank to default to the parent course's full_description attribute.", null=True)),
                ('min_effort', models.PositiveSmallIntegerField(help_text='Estimated minimum number of hours per week needed to complete a course run.', blank=True, null=True)),
                ('max_effort', models.PositiveSmallIntegerField(help_text='Estimated maximum number of hours per week needed to complete a course run.', blank=True, null=True)),
                ('pacing_type', models.CharField(db_index=True, blank=True, max_length=255, null=True, choices=[('self_paced', 'Self-paced'), ('instructor_paced', 'Instructor-paced')])),
                ('course', models.ForeignKey(related_name='course_runs', to='course_metadata.Course', on_delete=django.db.models.deletion.CASCADE)),
            ],
            options={
                'ordering': ('-modified', '-created'),
                'get_latest_by': 'modified',
                'abstract': False,
            },
        ),
        migrations.CreateModel(
            name='ExpectedLearningItem',
            fields=[
                ('id', models.AutoField(primary_key=True, auto_created=True, verbose_name='ID', serialize=False)),
                ('created', django_extensions.db.fields.CreationDateTimeField(auto_now_add=True, verbose_name='created')),
                ('modified', django_extensions.db.fields.ModificationDateTimeField(verbose_name='modified', auto_now=True)),
                ('value', models.CharField(max_length=255)),
            ],
            options={
                'abstract': False,
            },
        ),
        migrations.CreateModel(
            name='HistoricalCourse',
            fields=[
                ('id', models.IntegerField(auto_created=True, blank=True, verbose_name='ID', db_index=True)),
                ('created', django_extensions.db.fields.CreationDateTimeField(auto_now_add=True, verbose_name='created')),
                ('modified', django_extensions.db.fields.ModificationDateTimeField(verbose_name='modified', auto_now=True)),
                ('key', models.CharField(max_length=255, db_index=True)),
                ('title', models.CharField(default=None, blank=True, max_length=255, null=True)),
                ('short_description', models.CharField(default=None, blank=True, max_length=255, null=True)),
                ('full_description', models.TextField(default=None, blank=True, null=True)),
                ('history_id', models.AutoField(primary_key=True, serialize=False)),
                ('history_date', models.DateTimeField()),
                ('history_type', models.CharField(max_length=1, choices=[('+', 'Created'), ('~', 'Changed'), ('-', 'Deleted')])),
                ('history_user', models.ForeignKey(to=settings.AUTH_USER_MODEL, related_name='+', on_delete=django.db.models.deletion.SET_NULL, null=True)),
            ],
            options={
                'verbose_name': 'historical course',
                'ordering': ('-history_date', '-history_id'),
                'get_latest_by': 'history_date',
            },
        ),
        migrations.CreateModel(
            name='HistoricalCourseRun',
            fields=[
                ('id', models.IntegerField(auto_created=True, blank=True, verbose_name='ID', db_index=True)),
                ('created', django_extensions.db.fields.CreationDateTimeField(auto_now_add=True, verbose_name='created')),
                ('modified', django_extensions.db.fields.ModificationDateTimeField(verbose_name='modified', auto_now=True)),
                ('key', models.CharField(max_length=255, db_index=True)),
                ('title_override', models.CharField(default=None, blank=True, max_length=255, null=True, help_text="Title specific for this run of a course. Leave this value blank to default to the parent course's title.")),
                ('start', models.DateTimeField(blank=True, null=True)),
                ('end', models.DateTimeField(blank=True, null=True)),
                ('enrollment_start', models.DateTimeField(blank=True, null=True)),
                ('enrollment_end', models.DateTimeField(blank=True, null=True)),
                ('announcement', models.DateTimeField(blank=True, null=True)),
                ('short_description_override', models.CharField(default=None, blank=True, max_length=255, null=True, help_text="Short description specific for this run of a course. Leave this value blank to default to the parent course's short_description attribute.")),
                ('full_description_override', models.TextField(default=None, blank=True, help_text="Full description specific for this run of a course. Leave this value blank to default to the parent course's full_description attribute.", null=True)),
                ('min_effort', models.PositiveSmallIntegerField(help_text='Estimated minimum number of hours per week needed to complete a course run.', blank=True, null=True)),
                ('max_effort', models.PositiveSmallIntegerField(help_text='Estimated maximum number of hours per week needed to complete a course run.', blank=True, null=True)),
                ('pacing_type', models.CharField(db_index=True, blank=True, max_length=255, null=True, choices=[('self_paced', 'Self-paced'), ('instructor_paced', 'Instructor-paced')])),
                ('history_id', models.AutoField(primary_key=True, serialize=False)),
                ('history_date', models.DateTimeField()),
                ('history_type', models.CharField(max_length=1, choices=[('+', 'Created'), ('~', 'Changed'), ('-', 'Deleted')])),
                ('course', models.ForeignKey(db_constraint=False, to='course_metadata.Course', blank=True, related_name='+', on_delete=django.db.models.deletion.DO_NOTHING, null=True)),
                ('history_user', models.ForeignKey(to=settings.AUTH_USER_MODEL, related_name='+', on_delete=django.db.models.deletion.SET_NULL, null=True)),
            ],
            options={
                'verbose_name': 'historical course run',
                'ordering': ('-history_date', '-history_id'),
                'get_latest_by': 'history_date',
            },
        ),
        migrations.CreateModel(
            name='HistoricalOrganization',
            fields=[
                ('id', models.IntegerField(auto_created=True, blank=True, verbose_name='ID', db_index=True)),
                ('created', django_extensions.db.fields.CreationDateTimeField(auto_now_add=True, verbose_name='created')),
                ('modified', django_extensions.db.fields.ModificationDateTimeField(verbose_name='modified', auto_now=True)),
                ('key', models.CharField(max_length=255, db_index=True)),
                ('name', models.CharField(blank=True, max_length=255, null=True)),
                ('description', models.TextField(blank=True, null=True)),
                ('homepage_url', models.URLField(blank=True, max_length=255, null=True)),
                ('history_id', models.AutoField(primary_key=True, serialize=False)),
                ('history_date', models.DateTimeField()),
                ('history_type', models.CharField(max_length=1, choices=[('+', 'Created'), ('~', 'Changed'), ('-', 'Deleted')])),
                ('history_user', models.ForeignKey(to=settings.AUTH_USER_MODEL, related_name='+', on_delete=django.db.models.deletion.SET_NULL, null=True)),
            ],
            options={
                'verbose_name': 'historical organization',
                'ordering': ('-history_date', '-history_id'),
                'get_latest_by': 'history_date',
            },
        ),
        migrations.CreateModel(
            name='HistoricalPerson',
            fields=[
                ('id', models.IntegerField(auto_created=True, blank=True, verbose_name='ID', db_index=True)),
                ('created', django_extensions.db.fields.CreationDateTimeField(auto_now_add=True, verbose_name='created')),
                ('modified', django_extensions.db.fields.ModificationDateTimeField(verbose_name='modified', auto_now=True)),
                ('key', models.CharField(max_length=255, db_index=True)),
                ('name', models.CharField(blank=True, max_length=255, null=True)),
                ('title', models.CharField(blank=True, max_length=255, null=True)),
                ('bio', models.TextField(blank=True, null=True)),
                ('history_id', models.AutoField(primary_key=True, serialize=False)),
                ('history_date', models.DateTimeField()),
                ('history_type', models.CharField(max_length=1, choices=[('+', 'Created'), ('~', 'Changed'), ('-', 'Deleted')])),
                ('history_user', models.ForeignKey(to=settings.AUTH_USER_MODEL, related_name='+', on_delete=django.db.models.deletion.SET_NULL, null=True)),
            ],
            options={
                'verbose_name': 'historical person',
                'ordering': ('-history_date', '-history_id'),
                'get_latest_by': 'history_date',
            },
        ),
        migrations.CreateModel(
            name='HistoricalSeat',
            fields=[
                ('id', models.IntegerField(auto_created=True, blank=True, verbose_name='ID', db_index=True)),
                ('created', django_extensions.db.fields.CreationDateTimeField(auto_now_add=True, verbose_name='created')),
                ('modified', django_extensions.db.fields.ModificationDateTimeField(verbose_name='modified', auto_now=True)),
                ('type', models.CharField(max_length=63, choices=[('honor', 'Honor'), ('audit', 'Audit'), ('verified', 'Verified'), ('professional', 'Professional'), ('credit', 'Credit')])),
                ('price', models.DecimalField(decimal_places=2, default=0.0, max_digits=10)),
                ('upgrade_deadline', models.DateTimeField(blank=True, null=True)),
                ('credit_provider', models.CharField(blank=True, max_length=255, null=True)),
                ('credit_hours', models.IntegerField(blank=True, null=True)),
                ('history_id', models.AutoField(primary_key=True, serialize=False)),
                ('history_date', models.DateTimeField()),
                ('history_type', models.CharField(max_length=1, choices=[('+', 'Created'), ('~', 'Changed'), ('-', 'Deleted')])),
                ('course_run', models.ForeignKey(db_constraint=False, to='course_metadata.CourseRun', blank=True, related_name='+', on_delete=django.db.models.deletion.DO_NOTHING, null=True)),
                ('currency', models.ForeignKey(db_constraint=False, to='core.Currency', blank=True, related_name='+', on_delete=django.db.models.deletion.DO_NOTHING, null=True)),
                ('history_user', models.ForeignKey(to=settings.AUTH_USER_MODEL, related_name='+', on_delete=django.db.models.deletion.SET_NULL, null=True)),
            ],
            options={
                'verbose_name': 'historical seat',
                'ordering': ('-history_date', '-history_id'),
                'get_latest_by': 'history_date',
            },
        ),
        migrations.CreateModel(
            name='Image',
            fields=[
                ('id', models.AutoField(primary_key=True, auto_created=True, verbose_name='ID', serialize=False)),
                ('created', django_extensions.db.fields.CreationDateTimeField(auto_now_add=True, verbose_name='created')),
                ('modified', django_extensions.db.fields.ModificationDateTimeField(verbose_name='modified', auto_now=True)),
                ('src', models.URLField(max_length=255, unique=True)),
                ('description', models.CharField(blank=True, max_length=255, null=True)),
                ('height', models.IntegerField(blank=True, null=True)),
                ('width', models.IntegerField(blank=True, null=True)),
            ],
            options={
                'abstract': False,
            },
        ),
        migrations.CreateModel(
            name='LevelType',
            fields=[
                ('id', models.AutoField(primary_key=True, auto_created=True, verbose_name='ID', serialize=False)),
                ('created', django_extensions.db.fields.CreationDateTimeField(auto_now_add=True, verbose_name='created')),
                ('modified', django_extensions.db.fields.ModificationDateTimeField(verbose_name='modified', auto_now=True)),
                ('name', models.CharField(max_length=255, unique=True)),
            ],
            options={
                'abstract': False,
            },
        ),
        migrations.CreateModel(
            name='Organization',
            fields=[
                ('id', models.AutoField(primary_key=True, auto_created=True, verbose_name='ID', serialize=False)),
                ('created', django_extensions.db.fields.CreationDateTimeField(auto_now_add=True, verbose_name='created')),
                ('modified', django_extensions.db.fields.ModificationDateTimeField(verbose_name='modified', auto_now=True)),
                ('key', models.CharField(max_length=255, unique=True)),
                ('name', models.CharField(blank=True, max_length=255, null=True)),
                ('description', models.TextField(blank=True, null=True)),
                ('homepage_url', models.URLField(blank=True, max_length=255, null=True)),
                ('logo_image', models.ForeignKey(to='course_metadata.Image', blank=True, null=True, on_delete=django.db.models.deletion.CASCADE)),
            ],
            options={
                'ordering': ('-modified', '-created'),
                'get_latest_by': 'modified',
                'abstract': False,
            },
        ),
        migrations.CreateModel(
            name='Person',
            fields=[
                ('id', models.AutoField(primary_key=True, auto_created=True, verbose_name='ID', serialize=False)),
                ('created', django_extensions.db.fields.CreationDateTimeField(auto_now_add=True, verbose_name='created')),
                ('modified', django_extensions.db.fields.ModificationDateTimeField(verbose_name='modified', auto_now=True)),
                ('key', models.CharField(max_length=255, unique=True)),
                ('name', models.CharField(blank=True, max_length=255, null=True)),
                ('title', models.CharField(blank=True, max_length=255, null=True)),
                ('bio', models.TextField(blank=True, null=True)),
                ('organizations', models.ManyToManyField(blank=True, to='course_metadata.Organization')),
                ('profile_image', models.ForeignKey(to='course_metadata.Image', blank=True, null=True, on_delete=django.db.models.deletion.CASCADE)),
            ],
            options={
                'verbose_name_plural': 'People',
            },
        ),
        migrations.CreateModel(
            name='Prerequisite',
            fields=[
                ('id', models.AutoField(primary_key=True, auto_created=True, verbose_name='ID', serialize=False)),
                ('created', django_extensions.db.fields.CreationDateTimeField(auto_now_add=True, verbose_name='created')),
                ('modified', django_extensions.db.fields.ModificationDateTimeField(verbose_name='modified', auto_now=True)),
                ('name', models.CharField(max_length=255, unique=True)),
            ],
            options={
                'abstract': False,
            },
        ),
        migrations.CreateModel(
            name='Seat',
            fields=[
                ('id', models.AutoField(primary_key=True, auto_created=True, verbose_name='ID', serialize=False)),
                ('created', django_extensions.db.fields.CreationDateTimeField(auto_now_add=True, verbose_name='created')),
                ('modified', django_extensions.db.fields.ModificationDateTimeField(verbose_name='modified', auto_now=True)),
                ('type', models.CharField(max_length=63, choices=[('honor', 'Honor'), ('audit', 'Audit'), ('verified', 'Verified'), ('professional', 'Professional'), ('credit', 'Credit')])),
                ('price', models.DecimalField(decimal_places=2, default=0.0, max_digits=10)),
                ('upgrade_deadline', models.DateTimeField(blank=True, null=True)),
                ('credit_provider', models.CharField(blank=True, max_length=255, null=True)),
                ('credit_hours', models.IntegerField(blank=True, null=True)),
                ('course_run', models.ForeignKey(related_name='seats', to='course_metadata.CourseRun', on_delete=django.db.models.deletion.CASCADE)),
                ('currency', models.ForeignKey(to='core.Currency', on_delete=django.db.models.deletion.CASCADE)),
            ],
        ),
        migrations.CreateModel(
            name='Subject',
            fields=[
                ('id', models.AutoField(primary_key=True, auto_created=True, verbose_name='ID', serialize=False)),
                ('created', django_extensions.db.fields.CreationDateTimeField(auto_now_add=True, verbose_name='created')),
                ('modified', django_extensions.db.fields.ModificationDateTimeField(verbose_name='modified', auto_now=True)),
                ('name', models.CharField(max_length=255, unique=True)),
            ],
            options={
                'abstract': False,
            },
        ),
        migrations.CreateModel(
            name='SyllabusItem',
            fields=[
                ('id', models.AutoField(primary_key=True, auto_created=True, verbose_name='ID', serialize=False)),
                ('created', django_extensions.db.fields.CreationDateTimeField(auto_now_add=True, verbose_name='created')),
                ('modified', django_extensions.db.fields.ModificationDateTimeField(verbose_name='modified', auto_now=True)),
                ('value', models.CharField(max_length=255)),
                ('parent', models.ForeignKey(to='course_metadata.SyllabusItem', blank=True, related_name='children', null=True, on_delete=django.db.models.deletion.CASCADE)),
            ],
            options={
                'abstract': False,
            },
        ),
        migrations.CreateModel(
            name='Video',
            fields=[
                ('id', models.AutoField(primary_key=True, auto_created=True, verbose_name='ID', serialize=False)),
                ('created', django_extensions.db.fields.CreationDateTimeField(auto_now_add=True, verbose_name='created')),
                ('modified', django_extensions.db.fields.ModificationDateTimeField(verbose_name='modified', auto_now=True)),
                ('src', models.URLField(max_length=255, unique=True)),
                ('description', models.CharField(blank=True, max_length=255, null=True)),
                ('image', models.ForeignKey(to='course_metadata.Image', blank=True, null=True, on_delete=django.db.models.deletion.CASCADE)),
            ],
            options={
                'abstract': False,
            },
        ),
        migrations.AddField(
            model_name='historicalperson',
            name='profile_image',
            field=models.ForeignKey(db_constraint=False, to='course_metadata.Image', blank=True, related_name='+', on_delete=django.db.models.deletion.DO_NOTHING, null=True),
        ),
        migrations.AddField(
            model_name='historicalorganization',
            name='logo_image',
            field=models.ForeignKey(db_constraint=False, to='course_metadata.Image', blank=True, related_name='+', on_delete=django.db.models.deletion.DO_NOTHING, null=True),
        ),
        migrations.AddField(
            model_name='historicalcourserun',
            name='image',
            field=models.ForeignKey(db_constraint=False, to='course_metadata.Image', blank=True, related_name='+', on_delete=django.db.models.deletion.DO_NOTHING, null=True),
        ),
        migrations.AddField(
            model_name='historicalcourserun',
            name='language',
            field=models.ForeignKey(db_constraint=False, to='ietf_language_tags.LanguageTag', blank=True, related_name='+', on_delete=django.db.models.deletion.DO_NOTHING, null=True),
        ),
        migrations.AddField(
            model_name='historicalcourserun',
            name='syllabus',
            field=models.ForeignKey(db_constraint=False, to='course_metadata.SyllabusItem', blank=True, related_name='+', on_delete=django.db.models.deletion.DO_NOTHING, null=True),
        ),
        migrations.AddField(
            model_name='historicalcourserun',
            name='video',
            field=models.ForeignKey(db_constraint=False, to='course_metadata.Video', blank=True, related_name='+', on_delete=django.db.models.deletion.DO_NOTHING, null=True),
        ),
        migrations.AddField(
            model_name='historicalcourse',
            name='image',
            field=models.ForeignKey(db_constraint=False, to='course_metadata.Image', blank=True, related_name='+', on_delete=django.db.models.deletion.DO_NOTHING, null=True),
        ),
        migrations.AddField(
            model_name='historicalcourse',
            name='level_type',
            field=models.ForeignKey(db_constraint=False, to='course_metadata.LevelType', blank=True, related_name='+', on_delete=django.db.models.deletion.DO_NOTHING, null=True),
        ),
        migrations.AddField(
            model_name='historicalcourse',
            name='video',
            field=models.ForeignKey(db_constraint=False, to='course_metadata.Video', blank=True, related_name='+', on_delete=django.db.models.deletion.DO_NOTHING, null=True),
        ),
        migrations.AddField(
            model_name='courserun',
            name='image',
            field=models.ForeignKey(default=None, to='course_metadata.Image', blank=True, null=True, on_delete=django.db.models.deletion.CASCADE),
        ),
        migrations.AddField(
            model_name='courserun',
            name='instructors',
            field=sortedm2m.fields.SortedManyToManyField(help_text=None, blank=True, related_name='courses_instructed', to='course_metadata.Person'),
        ),
        migrations.AddField(
            model_name='courserun',
            name='language',
            field=models.ForeignKey(to='ietf_language_tags.LanguageTag', blank=True, null=True, on_delete=django.db.models.deletion.CASCADE),
        ),
        migrations.AddField(
            model_name='courserun',
            name='staff',
            field=sortedm2m.fields.SortedManyToManyField(help_text=None, blank=True, related_name='courses_staffed', to='course_metadata.Person'),
        ),
        migrations.AddField(
            model_name='courserun',
            name='syllabus',
            field=models.ForeignKey(default=None, to='course_metadata.SyllabusItem', blank=True, null=True, on_delete=django.db.models.deletion.CASCADE),
        ),
        migrations.AddField(
            model_name='courserun',
            name='transcript_languages',
            field=models.ManyToManyField(blank=True, related_name='transcript_courses', to='ietf_language_tags.LanguageTag'),
        ),
        migrations.AddField(
            model_name='courserun',
            name='video',
            field=models.ForeignKey(default=None, to='course_metadata.Video', blank=True, null=True, on_delete=django.db.models.deletion.CASCADE),
        ),
        migrations.AddField(
            model_name='courseorganization',
            name='organization',
            field=models.ForeignKey(to='course_metadata.Organization', on_delete=django.db.models.deletion.CASCADE),
        ),
        migrations.AddField(
            model_name='course',
            name='expected_learning_items',
            field=sortedm2m.fields.SortedManyToManyField(help_text=None, blank=True, to='course_metadata.ExpectedLearningItem'),
        ),
        migrations.AddField(
            model_name='course',
            name='image',
            field=models.ForeignKey(default=None, to='course_metadata.Image', blank=True, null=True, on_delete=django.db.models.deletion.CASCADE),
        ),
        migrations.AddField(
            model_name='course',
            name='level_type',
            field=models.ForeignKey(default=None, to='course_metadata.LevelType', blank=True, null=True, on_delete=django.db.models.deletion.CASCADE),
        ),
        migrations.AddField(
            model_name='course',
            name='organizations',
            field=models.ManyToManyField(blank=True, through='course_metadata.CourseOrganization', to='course_metadata.Organization'),
        ),
        migrations.AddField(
            model_name='course',
            name='prerequisites',
            field=models.ManyToManyField(blank=True, to='course_metadata.Prerequisite'),
        ),
        migrations.AddField(
            model_name='course',
            name='subjects',
            field=models.ManyToManyField(blank=True, to='course_metadata.Subject'),
        ),
        migrations.AddField(
            model_name='course',
            name='video',
            field=models.ForeignKey(default=None, to='course_metadata.Video', blank=True, null=True, on_delete=django.db.models.deletion.CASCADE),
        ),
        migrations.AlterUniqueTogether(
            name='seat',
            unique_together={('course_run', 'type', 'currency', 'credit_provider')},
        ),
        migrations.AlterUniqueTogether(
            name='courseorganization',
            unique_together={('course', 'organization', 'relation_type')},
        ),
        migrations.AlterIndexTogether(
            name='courseorganization',
            index_together={('course', 'relation_type')},
        ),
    ]
