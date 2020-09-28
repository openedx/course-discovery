from django_elasticsearch_dsl.registries import registry
from django_elasticsearch_dsl.signals import RealTimeSignalProcessor as OriginRealTimeSignalProcessor


class RealTimeSignalProcessor(OriginRealTimeSignalProcessor):
    """
    Custom realtime signal processor to keep fresh all es indexes.

    Allows adding specific business logic to prevent indexing or vice versa - to force it.

    Business cases:
        - do not synchronize `CourseRun` model if instance `type`
        is not marketable;
    """
    def handle_save(self, sender, instance, **kwargs):
        if sender._meta.model_name == 'courserun' and not instance.type.is_marketable:
            return
        registry.update(instance)
        registry.update_related(instance)
