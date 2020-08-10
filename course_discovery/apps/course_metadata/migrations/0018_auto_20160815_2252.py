import uuid

import django.db.models.deletion
import django_extensions.db.fields
from django.db import migrations, models


def delete_people(apps, schema_editor):
    Person = apps.get_model('course_metadata', 'Person')
    Person.objects.all().delete()


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0010_auto_20160731_0023'),
        ('course_metadata', '0017_auto_20160815_2135'),
    ]

    operations = [
        migrations.RunPython(delete_people, reverse_code=migrations.RunPython.noop),
        migrations.CreateModel(
            name='Position',
            fields=[
                ('id', models.AutoField(serialize=False, primary_key=True, verbose_name='ID', auto_created=True)),
                ('created', django_extensions.db.fields.CreationDateTimeField(auto_now_add=True, verbose_name='created')),
                ('modified', django_extensions.db.fields.ModificationDateTimeField(auto_now=True, verbose_name='modified')),
                ('title', models.CharField(max_length=255)),
                ('organization_override', models.CharField(max_length=255, blank=True, null=True)),
                ('organization', models.ForeignKey(null=True, to='course_metadata.Organization', blank=True, on_delete=django.db.models.deletion.CASCADE)),
            ],
            options={
                'ordering': ('-modified', '-created'),
                'abstract': False,
                'get_latest_by': 'modified',
            },
        ),
        migrations.RemoveField(
            model_name='historicalperson',
            name='email',
        ),
        migrations.RemoveField(
            model_name='historicalperson',
            name='key',
        ),
        migrations.RemoveField(
            model_name='historicalperson',
            name='name',
        ),
        migrations.RemoveField(
            model_name='historicalperson',
            name='profile_image',
        ),
        migrations.RemoveField(
            model_name='historicalperson',
            name='title',
        ),
        migrations.RemoveField(
            model_name='historicalperson',
            name='username',
        ),
        migrations.AddField(
            model_name='historicalperson',
            name='family_name',
            field=models.CharField(max_length=255, blank=True, null=True),
        ),
        migrations.AddField(
            model_name='historicalperson',
            name='given_name',
            field=models.CharField(default='', max_length=255),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name='historicalperson',
            name='partner',
            field=models.ForeignKey(on_delete=django.db.models.deletion.DO_NOTHING, null=True, db_constraint=False, to='core.Partner', related_name='+', blank=True),
        ),
        migrations.AddField(
            model_name='historicalperson',
            name='profile_image_url',
            field=models.URLField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='historicalperson',
            name='slug',
            field=django_extensions.db.fields.AutoSlugField(populate_from=('given_name', 'family_name'), blank=True, editable=False),
        ),
        migrations.AddField(
            model_name='historicalperson',
            name='uuid',
            field=models.UUIDField(default=uuid.uuid4, verbose_name='UUID', editable=False),
        ),
        migrations.AddField(
            model_name='person',
            name='family_name',
            field=models.CharField(max_length=255, blank=True, null=True),
        ),
        migrations.AddField(
            model_name='person',
            name='given_name',
            field=models.CharField(default='', max_length=255),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name='person',
            name='partner',
            field=models.ForeignKey(null=True, to='core.Partner', on_delete=django.db.models.deletion.CASCADE),
        ),
        migrations.AddField(
            model_name='person',
            name='profile_image_url',
            field=models.URLField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='person',
            name='slug',
            field=django_extensions.db.fields.AutoSlugField(populate_from=('given_name', 'family_name'), blank=True, editable=False),
        ),
        migrations.AddField(
            model_name='person',
            name='uuid',
            field=models.UUIDField(default=uuid.uuid4, verbose_name='UUID', editable=False),
        ),
        migrations.AlterUniqueTogether(
            name='person',
            unique_together={('partner', 'uuid')},
        ),
        migrations.AddField(
            model_name='position',
            name='person',
            field=models.OneToOneField(to='course_metadata.Person', on_delete=django.db.models.deletion.CASCADE),
        ),
        migrations.RemoveField(
            model_name='person',
            name='email',
        ),
        migrations.RemoveField(
            model_name='person',
            name='expertises',
        ),
        migrations.RemoveField(
            model_name='person',
            name='key',
        ),
        migrations.RemoveField(
            model_name='person',
            name='major_works',
        ),
        migrations.RemoveField(
            model_name='person',
            name='name',
        ),
        migrations.RemoveField(
            model_name='person',
            name='organizations',
        ),
        migrations.RemoveField(
            model_name='person',
            name='profile_image',
        ),
        migrations.RemoveField(
            model_name='person',
            name='title',
        ),
        migrations.RemoveField(
            model_name='person',
            name='username',
        ),
        migrations.DeleteModel(
            name='Expertise',
        ),
        migrations.DeleteModel(
            name='MajorWork',
        ),
    ]
