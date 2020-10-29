import django.db.models.deletion
import django_extensions.db.fields
import sortedm2m.fields
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('course_metadata', '0006_auto_20160719_2052'),
    ]

    operations = [
        migrations.CreateModel(
            name='CourseRunSocialNetwork',
            fields=[
                ('id', models.AutoField(primary_key=True, verbose_name='ID', auto_created=True, serialize=False)),
                ('created', django_extensions.db.fields.CreationDateTimeField(verbose_name='created', auto_now_add=True)),
                ('modified', django_extensions.db.fields.ModificationDateTimeField(auto_now=True, verbose_name='modified')),
                ('type', models.CharField(choices=[('facebook', 'Facebook'), ('twitter', 'Twitter'), ('blog', 'Blog'), ('others', 'Others')], db_index=True, max_length=15)),
                ('value', models.CharField(max_length=500)),
                ('course_run', models.ForeignKey(related_name='course_run_networks', to='course_metadata.CourseRun', on_delete=django.db.models.deletion.CASCADE)),
            ],
            options={
                'verbose_name_plural': 'CourseRun SocialNetwork',
            },
        ),
        migrations.CreateModel(
            name='Expertise',
            fields=[
                ('id', models.AutoField(primary_key=True, verbose_name='ID', auto_created=True, serialize=False)),
                ('created', django_extensions.db.fields.CreationDateTimeField(verbose_name='created', auto_now_add=True)),
                ('modified', django_extensions.db.fields.ModificationDateTimeField(auto_now=True, verbose_name='modified')),
                ('name', models.CharField(unique=True, max_length=255)),
            ],
            options={
                'abstract': False,
            },
        ),
        migrations.CreateModel(
            name='MajorWork',
            fields=[
                ('id', models.AutoField(primary_key=True, verbose_name='ID', auto_created=True, serialize=False)),
                ('created', django_extensions.db.fields.CreationDateTimeField(verbose_name='created', auto_now_add=True)),
                ('modified', django_extensions.db.fields.ModificationDateTimeField(auto_now=True, verbose_name='modified')),
                ('name', models.CharField(unique=True, max_length=255)),
            ],
            options={
                'abstract': False,
            },
        ),
        migrations.CreateModel(
            name='PersonSocialNetwork',
            fields=[
                ('id', models.AutoField(primary_key=True, verbose_name='ID', auto_created=True, serialize=False)),
                ('created', django_extensions.db.fields.CreationDateTimeField(verbose_name='created', auto_now_add=True)),
                ('modified', django_extensions.db.fields.ModificationDateTimeField(auto_now=True, verbose_name='modified')),
                ('type', models.CharField(choices=[('facebook', 'Facebook'), ('twitter', 'Twitter'), ('blog', 'Blog'), ('others', 'Others')], db_index=True, max_length=15)),
                ('value', models.CharField(max_length=500)),
            ],
            options={
                'verbose_name_plural': 'Person SocialNetwork',
            },
        ),
        migrations.AddField(
            model_name='course',
            name='learner_testimonial',
            field=models.CharField(help_text='A quote from a learner in the course, demonstrating the value of taking the course', null=True, blank=True, max_length=50),
        ),
        migrations.AddField(
            model_name='course',
            name='number',
            field=models.CharField(help_text='Course number format e.g CS002x, BIO1.1x, BIO1.2x', null=True, blank=True, max_length=50),
        ),
        migrations.AddField(
            model_name='historicalcourse',
            name='learner_testimonial',
            field=models.CharField(help_text='A quote from a learner in the course, demonstrating the value of taking the course', null=True, blank=True, max_length=50),
        ),
        migrations.AddField(
            model_name='historicalcourse',
            name='number',
            field=models.CharField(help_text='Course number format e.g CS002x, BIO1.1x, BIO1.2x', null=True, blank=True, max_length=50),
        ),
        migrations.AddField(
            model_name='historicalperson',
            name='email',
            field=models.EmailField(null=True, blank=True, max_length=255),
        ),
        migrations.AddField(
            model_name='historicalperson',
            name='username',
            field=models.CharField(null=True, blank=True, max_length=255),
        ),
        migrations.AddField(
            model_name='person',
            name='email',
            field=models.EmailField(null=True, blank=True, max_length=255),
        ),
        migrations.AddField(
            model_name='person',
            name='username',
            field=models.CharField(null=True, blank=True, max_length=255),
        ),
        migrations.AddField(
            model_name='personsocialnetwork',
            name='person',
            field=models.ForeignKey(related_name='person_networks', to='course_metadata.Person', on_delete=django.db.models.deletion.CASCADE),
        ),
        migrations.AddField(
            model_name='person',
            name='expertises',
            field=sortedm2m.fields.SortedManyToManyField(related_name='person_expertise', help_text=None, blank=True, to='course_metadata.Expertise'),
        ),
        migrations.AddField(
            model_name='person',
            name='major_works',
            field=sortedm2m.fields.SortedManyToManyField(related_name='person_works', help_text=None, blank=True, to='course_metadata.MajorWork'),
        ),
        migrations.AlterUniqueTogether(
            name='personsocialnetwork',
            unique_together={('person', 'type')},
        ),
        migrations.AlterUniqueTogether(
            name='courserunsocialnetwork',
            unique_together={('course_run', 'type')},
        ),
    ]
