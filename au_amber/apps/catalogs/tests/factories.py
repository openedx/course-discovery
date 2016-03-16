import factory
from factory.fuzzy import FuzzyText

from course_discovery.apps.catalogs.models import Catalog


class CatalogFactory(factory.DjangoModelFactory):
    class Meta(object):
        model = Catalog

    name = FuzzyText(prefix='catalog-name-')
    query = '{"query": {"match_all": {}}}'
