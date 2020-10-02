import factory
from factory.fuzzy import FuzzyText

from course_discovery.apps.catalogs.models import Catalog


class CatalogFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Catalog

    name = FuzzyText(prefix='catalog-name-')
    query = '*:*'

    @factory.post_generation
    def viewers(self, create, extracted, **kwargs):  # pylint: disable=method-hidden,unused-argument
        if create and extracted:
            self.viewers = extracted
