import uuid

import django.db.models.deletion
import django_extensions.db.fields
from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from django.db import migrations, models


def update_subjects(apps, schema_editor):
    Subject = apps.get_model('course_metadata', 'Subject')

    subjects = Subject.objects.filter(partner__isnull=True)

    if subjects.count() > 0:
        # We perform this check here to avoid issues with migrations for empty databases
        # (e.g. when running unit tests) that don't yet have a defined Partner.
        if not settings.DEFAULT_PARTNER_ID:
            raise ImproperlyConfigured('DEFAULT_PARTNER_ID must be defined!')

        Partner = apps.get_model('core', 'Partner')
        partner = Partner.objects.get(id=settings.DEFAULT_PARTNER_ID)

        # We iterate over all subjects, instead of calling .update(), to trigger slug generation
        for subject in subjects:
            subject.partner = partner
            subject.uuid = uuid.uuid4()
            subject.save()


class Migration(migrations.Migration):
    dependencies = [
        ('core', '0010_auto_20160731_0023'),
        ('course_metadata', '0012_create_seat_types'),
    ]

    operations = [
        migrations.AddField(
            model_name='subject',
            name='uuid',
            field=models.UUIDField(verbose_name='UUID', editable=False, default=uuid.uuid4),
        ),
        migrations.AddField(
            model_name='subject',
            name='banner_image_url',
            field=models.URLField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='subject',
            name='card_image_url',
            field=models.URLField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='subject',
            name='description',
            field=models.TextField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='subject',
            name='partner',
            field=models.ForeignKey(to='core.Partner', null=True, on_delete=django.db.models.deletion.CASCADE),
        ),
        migrations.AddField(
            model_name='subject',
            name='slug',
            field=django_extensions.db.fields.AutoSlugField(overwrite=True, editable=False, blank=True,
                                                            populate_from='name'),
        ),
        migrations.AddField(
            model_name='subject',
            name='subtitle',
            field=models.CharField(blank=True, max_length=255, null=True),
        ),
        migrations.AlterField(
            model_name='subject',
            name='name',
            field=models.CharField(max_length=255),
        ),
        migrations.AlterUniqueTogether(
            name='subject',
            unique_together={('partner', 'name'), ('partner', 'slug'), ('partner', 'uuid')},
        ),
        migrations.RunPython(update_subjects, reverse_code=migrations.RunPython.noop),
        migrations.AlterField(
            model_name='subject',
            name='slug',
            field=django_extensions.db.fields.AutoSlugField(populate_from='name', editable=False,
                                                            help_text='Leave this field blank to have the value generated automatically.',
                                                            blank=True),
        ),
        migrations.AlterField(
            model_name='subject',
            name='partner',
            field=models.ForeignKey(to='core.Partner', on_delete=django.db.models.deletion.CASCADE),
        ),
    ]
