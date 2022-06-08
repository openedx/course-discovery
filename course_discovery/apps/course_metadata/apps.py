from django.apps import AppConfig
from django.db.models.signals import post_migrate
from PIL import ImageFile


class CourseMetadataConfig(AppConfig):
    name = 'course_discovery.apps.course_metadata'
    verbose_name = 'Course Metadata'

    def ready(self):
        super().ready()
        # We need to add this setting because, since MM programs we are accepting banner
        # images with height less than 480 max. In order to accept those images, we need
        # to allow PIL to work with these images correctly by setting this variable true
        ImageFile.LOAD_TRUNCATED_IMAGES = True
        # noinspection PyUnresolvedReferences
        import course_discovery.apps.course_metadata.signals  # pylint: disable=import-outside-toplevel,unused-import
        post_migrate.connect(
            course_discovery.apps.course_metadata.signals.populate_topic_name, sender=self
        )
