from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('course_metadata', '0024_auto_20160901_1426'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='program',
            name='category',
        ),
    ]
