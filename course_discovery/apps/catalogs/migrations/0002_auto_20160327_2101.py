from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('catalogs', '0001_initial'),
    ]

    operations = [
        migrations.AlterModelOptions(
            name='catalog',
            options={'ordering': ('-modified', '-created'), 'permissions': (('view_catalog', 'Can view catalog'),), 'get_latest_by': 'modified'},
        ),
    ]
