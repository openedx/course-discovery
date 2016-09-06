from django.apps import AppConfig


class CourseMetadataConfig(AppConfig):
    name = 'course_discovery.apps.course_metadata'
    verbose_name = 'Course Metadata'

    def ready(self):
        super(CourseMetadataConfig, self).ready()
        # noinspection PyUnresolvedReferences
        import course_discovery.apps.course_metadata.signals  # pylint: disable=unused-variable
