from django.apps import AppConfig


class PublisherAppConfig(AppConfig):
    name = 'course_discovery.apps.publisher'
    verbose_name = 'Publisher'

    def ready(self):
        super().ready()
        # noinspection PyUnresolvedReferences
        import course_discovery.apps.publisher.signals  # pylint: disable=import-outside-toplevel,unused-import
