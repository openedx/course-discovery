# -*- coding: utf-8 -*-
from __future__ import unicode_literals

import pycountry
from django.db import migrations


def add_currencies(apps, schema_editor):
    """ Populates the currency table.

    Data is pulled from pycountry. X currencies are not included given their limited use, and a desire
    to limit the size of the options displayed in Django admin.
    """
    Currency = apps.get_model('core', 'Currency')
    Currency.objects.bulk_create(
        [Currency(code=currency.letter, name=currency.name) for currency in pycountry.currencies if
            not currency.letter.startswith('X')]
    )


def remove_currencies(apps, schema_editor):
    """ Deletes all rows in the currency table. """
    Currency = apps.get_model('core', 'Currency')
    Currency.objects.all().delete()


class Migration(migrations.Migration):
    dependencies = [
        ('core', '0004_currency'),
    ]

    operations = [
        migrations.RunPython(add_currencies, remove_currencies),
    ]
