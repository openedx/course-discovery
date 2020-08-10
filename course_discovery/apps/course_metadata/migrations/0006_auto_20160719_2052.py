from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ('course_metadata', '0005_auto_20160713_0113'),
    ]

    operations = [
        migrations.RenameField(
            model_name='program',
            old_name='name',
            new_name='title'
        ),
        migrations.AlterField(
            model_name='program',
            name='title',
            field=models.CharField(unique=True, help_text='The user-facing display title for this Program.',
                                   max_length=255),
        ),
    ]
