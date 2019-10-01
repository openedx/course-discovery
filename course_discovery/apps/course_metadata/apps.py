from django.apps import AppConfig
from PIL import ImageFile


class CourseMetadataConfig(AppConfig):
    name = 'course_discovery.apps.course_metadata'
    verbose_name = 'Course Metadata'

    def ready(self):
        super(CourseMetadataConfig, self).ready()
        # We need to add this setting because, since MM programs we are accepting banner
        # images with height less than 480 max. In order to accept those images, we need
        # to allow PIL to work with these images correctly by setting this variable true
        ImageFile.LOAD_TRUNCATED_IMAGES = True
        # noinspection PyUnresolvedReferences
        import course_discovery.apps.course_metadata.signals  # pylint: disable=import-outside-toplevel,unused-import
