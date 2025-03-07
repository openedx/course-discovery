# Generated by Django 4.2.19 on 2025-03-03 12:30

# Refrences:
# https://ss64.com/locale.html
# https://en.wikipedia.org/wiki/IETF_language_tag
# https://en.wikipedia.org/wiki/List_of_ISO_639_language_codes
# https://localizely.com/language-code/zh/

from django.db import migrations

LANGTAGS = (
    ("Afar", "aa"),
    ("Abkhazian", "ab"),
    ("Avestan", "ae"),
    ("Akan", "ak"),
    ("Amharic", "am"),
    ("Aragonese", "an"),
    ("Avaric", "av"),
    ("Azeri", "az"),
    ("Bashkir", "ba"),
    ("Bambara", "bm"),
    ("Bosnian", "bs"),
    ("Chechen", "ce"),
    ('English', 'en'),
    ("Ewe", "ee"),
    ("Esperanto", "eo"),
    ("Spanish - Latin America and Caribbean", "es-419"),
    ("Fulah", "ff"),
    ("Frisian", "fy"),
    ("Galician", "gl"),
    ("Gujarati", "gu"),
    ("Haitian", "ht"),
    ("Herero", "hz"),
    ("Inupiaq", "ik"),
    ("Georgian", "ka"),
    ("Kazakh", "kk"),
    ("Kannada", "kn"),
    ("Kurdish", "ku"),
    ("Morisyen", "mfe"),
    ("Maori", "mi"),
    ("Mongolian", "mn"),
    ("Malay", "ms"),
    ("Burmese", "my"),
    ("Nauru", "na"),
    ("Nepali", "ne"),
    ("Dutch", "nl"),
    ("Norwegian", "no"),
    ("Odia", "or"),
    ("Pashto", "ps"),
    ("Serbian", "sr"),
    ("Sundanese", "su"),
    ("Swedish", "sv"),
    ('Uzbek', 'uz'),
    ("Yoruba", "yo"),
    ("Chinese - Simplified, China", "zh-Hans-CN"),
    ("Chinese - Simplified, Hong Kong", "zh-Hans-HK"),
    ("Chinese - Simplified, Taiwan", "zh-Hant-TW"),
)

def add_languages_tags(apps, schema_editor):  # pylint: disable=unused-argument
    LanguageTag = apps.get_model('ietf_language_tags', 'LanguageTag')
    LanguageTagTranslation = apps.get_model('ietf_language_tags', 'LanguageTagTranslation')

    for name, code in LANGTAGS:
        LanguageTag.objects.update_or_create(code=code, defaults={'name': name})
        LanguageTagTranslation.objects.update_or_create(
            master=LanguageTag.objects.get(code=code),
            language_code='en',
            defaults={'name_t': name}
        )

class Migration(migrations.Migration):

    dependencies = [
        ('ietf_language_tags', '0006_auto_20231016_1044'),
    ]

    operations = [
        migrations.RunPython(add_languages_tags, migrations.RunPython.noop),
    ]
