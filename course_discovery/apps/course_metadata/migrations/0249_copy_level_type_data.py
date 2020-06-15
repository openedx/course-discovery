# Generated by Django 2.2.12 on 2020-04-30 12:00


import logging

from django.conf import settings
from django.core.exceptions import ObjectDoesNotExist
from django.db import migrations

logger = logging.getLogger(__name__)


def forwards_func(apps, schema_editor):
    LevelType = apps.get_model('course_metadata', 'LevelType')
    LevelTypeTranslation = apps.get_model('course_metadata', 'LevelTypeTranslation')

    for level_type in LevelType.objects.all():
        LevelTypeTranslation.objects.update_or_create(
            master_id=level_type.pk,
            language_code=settings.PARLER_DEFAULT_LANGUAGE_CODE,
            name_t=level_type.name,
        )


def backwards_func(apps, schema_editor):
    LevelType = apps.get_model('course_metadata', 'LevelType')
    LevelTypeTranslation = apps.get_model('course_metadata', 'LevelTypeTranslation')

    for level_type in LevelType.objects.all():
        try:
            translation = LevelTypeTranslation.objects.get(master_id=level_type.pk, language_code=settings.LANGUAGE_CODE)
            level_type.name = translation.name_t
            level_type.save()  # Note this only calls Model.save()
        except ObjectDoesNotExist:
            # nothing to migrate
            logger.warning('Migrating data from LevelTypeTranslation for master_id={} DoesNotExist'.format(level_type.pk))



class Migration(migrations.Migration):

    dependencies = [
        ('course_metadata', '0248_auto_20200430_1211'),
    ]

    operations = [
        migrations.RunPython(forwards_func, backwards_func),
    ]
