import taggit.managers
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('taggit', '0002_auto_20150616_2121'),
        ('course_metadata', '0016_auto_20160815_1438'),
    ]

    operations = [
        migrations.AddField(
            model_name='historicalorganization',
            name='marketing_url_path',
            field=models.CharField(null=True, max_length=255, blank=True),
        ),
        migrations.AddField(
            model_name='organization',
            name='marketing_url_path',
            field=models.CharField(null=True, max_length=255, blank=True),
        ),
        migrations.AddField(
            model_name='organization',
            name='tags',
            field=taggit.managers.TaggableManager(verbose_name='Tags', to='taggit.Tag', through='taggit.TaggedItem', help_text='A comma-separated list of tags.', blank=True),
        ),
    ]
