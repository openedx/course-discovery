from __future__ import unicode_literals

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('course_metadata', '0219_leveltype_ordering'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='leveltype',
            name='order',
        ),
    ]
