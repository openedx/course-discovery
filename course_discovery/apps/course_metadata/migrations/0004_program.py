import uuid

import django_extensions.db.fields
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('course_metadata', '0003_auto_20160523_1422'),
    ]

    operations = [
        migrations.CreateModel(
            name='Program',
            fields=[
                ('id', models.AutoField(verbose_name='ID', primary_key=True, serialize=False, auto_created=True)),
                ('created', django_extensions.db.fields.CreationDateTimeField(auto_now_add=True, verbose_name='created')),
                ('modified', django_extensions.db.fields.ModificationDateTimeField(verbose_name='modified', auto_now=True)),
                ('uuid', models.UUIDField(unique=True, default=uuid.uuid4, blank=True, editable=False)),
                ('name', models.CharField(max_length=255, help_text='The user-facing display name for this Program.', unique=True)),
                ('subtitle', models.CharField(help_text='A brief, descriptive subtitle for the Program.', max_length=255, blank=True)),
                ('category', models.CharField(help_text='The category / type of Program.', max_length=32)),
                ('status', models.CharField(help_text='The lifecycle status of this Program.', max_length=24)),
                ('marketing_slug', models.CharField(help_text='Slug used to generate links to the marketing site', max_length=255, blank=True)),
                ('organizations', models.ManyToManyField(to='course_metadata.Organization', blank=True)),
            ],
            options={
                'ordering': ('-modified', '-created'),
                'abstract': False,
                'get_latest_by': 'modified',
            },
        ),
    ]
