from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('course_metadata', '0218_leveltype_sort_value_copy_values'),
    ]

    operations = [
        migrations.AlterModelOptions(
            name='leveltype',
            options={'ordering': ('sort_value',)},
        ),
    ]
