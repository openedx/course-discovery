import taggit.managers
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('taggit', '0002_auto_20150616_2121'),
        ('publisher', '0011_userattributes'),
    ]

    operations = [

        # This is custom alteration to make migration reversible
        migrations.AlterField(
            model_name='courserun',
            name='keywords',
            field=models.TextField(verbose_name='keywords', default=None, blank=True),
            preserve_default=False,
        ),
        migrations.AlterField(
            model_name='historicalcourserun',
            name='keywords',
            field=models.TextField(verbose_name='keywords', default=None, blank=True),
            preserve_default=False,
        ),
        # end custom migration

        migrations.RemoveField(
            model_name='courserun',
            name='is_seo_review',
        ),
        migrations.RemoveField(
            model_name='courserun',
            name='keywords',
        ),
        migrations.RemoveField(
            model_name='historicalcourserun',
            name='is_seo_review',
        ),
        migrations.RemoveField(
            model_name='historicalcourserun',
            name='keywords',
        ),
        migrations.AddField(
            model_name='course',
            name='is_seo_review',
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name='course',
            name='keywords',
            field=taggit.managers.TaggableManager(help_text='A comma-separated list of tags.', verbose_name='keywords', through='taggit.TaggedItem', blank=True, to='taggit.Tag'),
        ),
        migrations.AddField(
            model_name='historicalcourse',
            name='is_seo_review',
            field=models.BooleanField(default=False),
        ),
    ]
