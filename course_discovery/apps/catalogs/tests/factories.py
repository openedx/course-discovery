import factory
from course_discovery.apps.catalogs.models import Catalog
from factory.fuzzy import FuzzyText


class CatalogFactory(factory.DjangoModelFactory):
    class Meta(object):
        model = Catalog

    name = FuzzyText(prefix='catalog-name-')
    query = '*:*'

    @factory.post_generation
    def viewers(self, create, extracted, **kwargs):  # pylint: disable=method-hidden,unused-argument
        if create and extracted:
            self.viewers = extracted
