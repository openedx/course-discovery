from abc import ABC, abstractmethod, abstractproperty

from django_elasticsearch_dsl.registries import registry
from django_elasticsearch_dsl.signals import RealTimeSignalProcessor as OriginRealTimeSignalProcessor


class IndexForbiddenException(Exception):
    """
    Raised if it is impossible to add/modify an object to an Elasticsearch index.
    """


class RegistryUpdateHandler(ABC):
    """
    Abstract index update handler.

    All handles must inherit from it. It is the last in the chain of handlers.
    Defines the structure and interfaces of the handlers.
    Updates an elasticsearch index.

    Implements pattern 'Chain of responsibilities.'
    """

    @abstractproperty
    def expected_models(self):
        pass

    __next_handler = None

    def set_next(self, handler):
        self.__next_handler = handler
        return handler

    # pylint: disable=inconsistent-return-statements
    @abstractmethod
    def handle(self, sender, instance, **kwargs):
        if self.__next_handler:
            return self.__next_handler.handle(sender, instance, **kwargs)
        registry.update(instance)
        registry.update_related(instance)


class MarketableHandler(RegistryUpdateHandler):
    """
    Index update handler.

    Responsible for ensuring that all 'courserun' models are not indexed
    if they are not marketable.
    """

    expected_models = ('courserun',)

    def handle(self, sender, instance, **kwargs):
        if sender._meta.model_name in self.expected_models and not instance.type.is_marketable:
            raise IndexForbiddenException("Requested to index object is not marketable.")

        return super().handle(sender, instance, **kwargs)


class DraftHandler(RegistryUpdateHandler):
    """
    Index update handler.

    Responsible for ensuring that all `CourseRun`, `Course` models are not indexed
    if they are marked as Draft.
    """

    expected_models = ('courserun', 'course',)

    def handle(self, sender, instance, **kwargs):
        if sender._meta.model_name in self.expected_models and instance.draft:
            raise IndexForbiddenException("Requested to index object is marked as draft.")

        return super().handle(sender, instance, **kwargs)


class RealTimeSignalProcessor(OriginRealTimeSignalProcessor):
    """
    Custom realtime signal processor to keep fresh all es indexes.

    Allows adding specific business logic to prevent indexing or vice versa - to force it.

    Business cases:
        - do not synchronize `CourseRun` model if instance `type` is not marketable;
        - do not synchronize `CourseRun` and `Course` models if instance `type` are marked as Draft;
    """

    def handle_save(self, sender, instance, **kwargs):
        index_updater = self.build_index_updater()
        try:
            index_updater.handle(sender, instance, **kwargs)
        except IndexForbiddenException:
            pass

    @staticmethod
    def build_index_updater():
        """
        Build a chain of handlers.

        Each handler must either prevent a index from being updated, or
        pass it to another handler.
        The last handler in the chain is updating the index.

        Implements pattern 'Chain of responsibilities.'
        """
        market_handler = MarketableHandler()
        draft_handler = DraftHandler()
        market_handler.set_next(draft_handler)

        return market_handler
