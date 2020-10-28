from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('course_metadata', '0009_auto_20160725_1751'),
    ]

    operations = [
        migrations.AlterField(
            model_name='program',
            name='marketing_slug',
            field=models.CharField(db_index=True, blank=True, help_text='Slug used to generate links to the marketing site', max_length=255),
        ),
    ]
