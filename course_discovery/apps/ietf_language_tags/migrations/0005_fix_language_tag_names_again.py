from django.db import migrations


def fix_tag_names(apps, schema_editor):
    """ Replace dashes (—) in tag names with hyphens (-)."""
    LanguageTag = apps.get_model('ietf_language_tags', 'LanguageTag')

    for tag in LanguageTag.objects.all():
        tag.name = tag.name.replace('–', '-')
        tag.save()


class Migration(migrations.Migration):
    dependencies = [
        ('ietf_language_tags', '0004_add_chinese_tags'),
    ]

    operations = [
        migrations.RunPython(fix_tag_names, migrations.RunPython.noop),
    ]
