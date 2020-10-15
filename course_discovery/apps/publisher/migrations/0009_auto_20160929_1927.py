import django.db.models.deletion
import stdimage.models
from django.conf import settings
from django.db import migrations, models

import course_discovery.apps.course_metadata.utils


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('ietf_language_tags', '0005_fix_language_tag_names_again'),
        ('publisher', '0008_auto_20160928_1015'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='courserun',
            name='seo_review',
        ),
        migrations.RemoveField(
            model_name='historicalcourserun',
            name='seo_review',
        ),
        migrations.AddField(
            model_name='course',
            name='image',
            field=stdimage.models.StdImageField(null=True, blank=True, upload_to=course_discovery.apps.course_metadata.utils.UploadToFieldNamePath('number', path='media/publisher/courses/images')),
        ),
        migrations.AddField(
            model_name='course',
            name='team_admin',
            field=models.ForeignKey(related_name='team_admin_user', null=True, to=settings.AUTH_USER_MODEL, blank=True, on_delete=django.db.models.deletion.CASCADE),
        ),
        migrations.AddField(
            model_name='courserun',
            name='is_seo_review',
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name='courserun',
            name='video_language',
            field=models.ForeignKey(related_name='video_language', null=True, to='ietf_language_tags.LanguageTag', blank=True, on_delete=django.db.models.deletion.CASCADE),
        ),
        migrations.AddField(
            model_name='historicalcourse',
            name='image',
            field=models.TextField(max_length=100, null=True, blank=True),
        ),
        migrations.AddField(
            model_name='historicalcourse',
            name='team_admin',
            field=models.ForeignKey(related_name='+', null=True, db_constraint=False, to=settings.AUTH_USER_MODEL, on_delete=django.db.models.deletion.DO_NOTHING, blank=True),
        ),
        migrations.AddField(
            model_name='historicalcourserun',
            name='is_seo_review',
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name='historicalcourserun',
            name='video_language',
            field=models.ForeignKey(related_name='+', null=True, db_constraint=False, to='ietf_language_tags.LanguageTag', on_delete=django.db.models.deletion.DO_NOTHING, blank=True),
        ),
    ]
