import stdimage.models
from django.db import migrations, models

import course_discovery.apps.course_metadata.utils


class Migration(migrations.Migration):

    dependencies = [
        ('course_metadata', '0019_program_banner_image'),
    ]

    operations = [
        migrations.AddField(
            model_name='program',
            name='credit_redemption_overview',
            field=models.TextField(null=True, help_text='The description of credit redemption for courses in program', blank=True),
        ),
        migrations.AlterField(
            model_name='program',
            name='banner_image',
            field=stdimage.models.StdImageField(null=True, blank=True, upload_to=course_discovery.apps.course_metadata.utils.UploadToFieldNamePath('uuid', path='media/programs/banner_images')),
        ),
        migrations.AlterField(
            model_name='program',
            name='courses',
            field=models.ManyToManyField(related_name='programs', to='course_metadata.Course'),
        ),
    ]
