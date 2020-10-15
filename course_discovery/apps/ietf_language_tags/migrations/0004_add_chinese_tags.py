from django.db import migrations

LANGTAGS = (
    ("Chinese - Mandarin", "zh-cmn"),
    ("Chinese - Simplified", "zh-Hans"),
    ("Chinese - Traditional", "zh-Hant"),
)


def add_language_tags(apps, schema_editor):
    LanguageTag = apps.get_model('ietf_language_tags', 'LanguageTag')

    for name, code in LANGTAGS:
        LanguageTag.objects.update_or_create(code=code, defaults={'name': name})


def drop_language_tags(apps, schema_editor):
    LanguageTag = apps.get_model('ietf_language_tags', 'LanguageTag')

    codes = [code for __, code in LANGTAGS]
    LanguageTag.objects.filter(code__in=codes).delete()


class Migration(migrations.Migration):
    dependencies = [
        ('ietf_language_tags', '0003_fix_language_tag_names'),
    ]

    operations = [
        migrations.RunPython(add_language_tags, drop_language_tags)
    ]
