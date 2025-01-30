from django.apps import AppConfig


class TaggingConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'course_discovery.apps.tagging'

    def ready(self):
        super().ready()
        import course_discovery.apps.tagging.signals  # pylint: disable=import-outside-toplevel,unused-import
