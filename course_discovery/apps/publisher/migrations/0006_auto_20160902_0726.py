from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('publisher', '0005_auto_20160901_0003'),
    ]

    operations = [
        migrations.AlterModelOptions(
            name='course',
            options={'permissions': (('view_course', 'Can view course'),), 'ordering': ('-modified', '-created'), 'get_latest_by': 'modified'},
        ),
    ]
