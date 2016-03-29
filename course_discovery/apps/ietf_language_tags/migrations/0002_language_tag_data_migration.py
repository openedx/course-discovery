# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models

# Set of language names, language tags.   Source: http://ss64.com/locale.html
LANGTAGS = (
    ("Afrikaans", "af"),
    ("Albanian", "sq"),
    ("Arabic – Algeria", "ar-dz"),
    ("Arabic – Bahrain", "ar-bh"),
    ("Arabic – Egypt", "ar-eg"),
    ("Arabic – Iraq", "ar-iq"),
    ("Arabic – Jordan", "ar-jo"),
    ("Arabic – Kuwait", "ar-kw"),
    ("Arabic – Lebanon", "ar-lb"),
    ("Arabic – Libya", "ar-ly"),
    ("Arabic – Morocco", "ar-ma"),
    ("Arabic – Oman", "ar-om"),
    ("Arabic – Qatar", "ar-qa"),
    ("Arabic – Saudi Arabia", "ar-sa"),
    ("Arabic – Syria", "ar-sy"),
    ("Arabic – Tunisia", "ar-tn"),
    ("Arabic – United Arab Emirates", "ar-ae"),
    ("Arabic – Yemen", "ar-ye"),
    ("Armenian", "hy"),
    ("Azeri – Latin", "az-az"),
    ("Basque (Basque)", "eu"),
    ("Belarusian", "be"),
    ("Bulgarian", "bg"),
    ("Catalan", "ca"),
    ("Chinese – China", "zh-cn"),
    ("Chinese – Hong Kong SAR", "zh-hk"),
    ("Chinese – Macau SAR", "zh-mo"),
    ("Chinese – Singapore", "zh-sg"),
    ("Chinese – Taiwan", "zh-tw"),
    ("Croatian", "hr"),
    ("Czech", "cs"),
    ("Danish", "da"),
    ("Dutch – Belgium", "nl-be"),
    ("Dutch – Netherlands", "nl-nl"),
    ("English – Australia", "en-au"),
    ("English – Belize", "en-bz"),
    ("English – Canada", "en-ca"),
    ("English – Caribbean", "en-cb"),
    ("English – India", "en-in"),
    ("English – Ireland", "en-ie"),
    ("English – Jamaica", "en-jm"),
    ("English – Malaysia", "en-my"),
    ("English – New Zealand", "en-nz"),
    ("English – Phillippines", "en-ph"),
    ("English – Singapore", "en-sg"),
    ("English – Southern Africa", "en-za"),
    ("English – Trinidad", "en-tt"),
    ("English – Great Britain", "en-gb"),
    ("English – United States", "en-us"),
    ("English – Zimbabwe", "en-zw"),
    ("Estonian", "et"),
    ("Farsi", "fa"),
    ("Finnish", "fi"),
    ("Faroese", "fo"),
    ("French – France", "fr-fr"),
    ("French – Belgium", "fr-be"),
    ("French – Canada", "fr-ca"),
    ("French – Luxembourg", "fr-lu"),
    ("French – Switzerland", "fr-ch"),
    ("Irish – Ireland", "gd-ie"),
    ("Scottish Gaelic – United Kingdom", "gd"),
    ("German – Germany", "de-de"),
    ("German – Austria", "de-at"),
    ("German – Liechtenstein", "de-li"),
    ("German – Luxembourg", "de-lu"),
    ("German – Switzerland", "de-ch"),
    ("Greek", "el"),
    ("Hebrew", "he"),
    ("Hindi", "hi"),
    ("Hungarian", "hu"),
    ("Icelandic", "is"),
    ("Indonesian", "id"),
    ("Italian – Italy", "it-it"),
    ("Italian – Switzerland", "it-ch"),
    ("Japanese", "ja"),
    ("Korean", "ko"),
    ("Latvian", "lv"),
    ("Lithuanian", "lt"),
    ("F.Y.R.O. Macedonia", "mk"),
    ("Malay – Malaysia", "ms-my"),
    ("Malay – Brunei", "ms-bn"),
    ("Maltese", "mt"),
    ("Marathi", "mr"),
    ("Norwegian – Bokmål", "nb-no"),
    ("Norwegian – Nynorsk", "nn-no"),
    ("Polish", "pl"),
    ("Portuguese – Portugal", "pt-pt"),
    ("Portuguese – Brazil", "pt-br"),
    ("Raeto-Romance", "rm"),
    ("Romanian – Romania", "ro"),
    ("Romanian – Republic of Moldova", "ro-mo"),
    ("Russian", "ru"),
    ("Russian – Republic of Moldova", "ru-mo"),
    ("Sanskrit", "sa"),
    ("Serbian – Latin", "sr-sp"),
    ("Setsuana", "tn"),
    ("Slovenian", "sl"),
    ("Slovak", "sk"),
    ("Sorbian", "sb"),
    ("Spanish – Spain (Modern)", "es-es"),
    ("Spanish – Spain (Traditional)", "&nbsp;"),
    ("Spanish – Argentina", "es-ar"),
    ("Spanish – Bolivia", "es-bo"),
    ("Spanish – Chile", "es-cl"),
    ("Spanish – Colombia", "es-co"),
    ("Spanish – Costa Rica", "es-cr"),
    ("Spanish – Dominican Republic", "es-do"),
    ("Spanish – Ecuador", "es-ec"),
    ("Spanish – Guatemala", "es-gt"),
    ("Spanish – Honduras", "es-hn"),
    ("Spanish – Mexico", "es-mx"),
    ("Spanish – Nicaragua", "es-ni"),
    ("Spanish – Panama", "es-pa"),
    ("Spanish – Peru", "es-pe"),
    ("Spanish – Puerto Rico", "es-pr"),
    ("Spanish – Paraguay", "es-py"),
    ("Spanish – El Salvador", "es-sv"),
    ("Spanish – Uruguay", "es-uy"),
    ("Spanish – Venezuela", "es-ve"),
    ("Southern Sotho", "st"),
    ("Swahili", "sw"),
    ("Swedish – Sweden", "sv-se"),
    ("Swedish – Finland", "sv-fi"),
    ("Tamil", "ta"),
    ("Tatar", "tt"),
    ("Thai", "th"),
    ("Turkish", "tr"),
    ("Tsonga", "ts"),
    ("Ukrainian", "uk"),
    ("Urdu", "ur"),
    ("Uzbek – Latin", "uz-uz"),
    ("Vietnamese", "vi"),
    ("Xhosa", "xh"),
    ("Yiddish", "yi"),
    ("Zulu", "zu"),
)


def add_language_tags(apps, schema_editor):
    LanguageTag = apps.get_model('ietf_language_tags', 'LanguageTag')

    for name, lcid in LANGTAGS:
        langtag, __ = LanguageTag.objects.get_or_create(id=lcid)
        langtag.name = name
        langtag.save()


def drop_language_tags(apps, schema_editor):
    LanguageTag = apps.get_model('ietf_language_tags', 'LanguageTag')

    lcids = [lcid for __, lcid in LANGTAGS]
    LanguageTag.objects.filter(id__in=lcids).delete()


class Migration(migrations.Migration):

    dependencies = [
        ('ietf_language_tags', '0001_initial'),
    ]

    operations = [
        migrations.RunPython(add_language_tags, drop_language_tags)
    ]
