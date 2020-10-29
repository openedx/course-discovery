import stdimage.models
from course_discovery.apps.course_metadata.utils import UploadToFieldNamePath
from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('course_metadata', '0018_auto_20160815_2252'),
    ]

    operations = [
        migrations.AddField(
            model_name='program',
            name='banner_image',
            field=stdimage.models.StdImageField(upload_to=UploadToFieldNamePath('uuid', path='/media/programs/banner_images'), null=True, blank=True),
        ),
    ]
