from django.core.management import call_command
from django.test import TestCase
from django_elasticsearch_dsl.registries import registry

from course_discovery.apps.core.tests.mixins import ElasticsearchTestMixin

LOGGER_NAME = 'courses.management.commands.install_es_indexes'


class InstallEsIndexesCommandTests(ElasticsearchTestMixin, TestCase):

    def test_create_index(self):
        """ Verify the app sets the alias and creates a new index. """
        for index in registry.get_indices():
            # pylint: disable=protected-access
            index_alias = index.get_alias()
            index_name, *_ = index_alias.keys()
            index._name = index_name
            self.es.indices.delete(index=index._name, ignore=404)
            assert not self.es.indices.exists(index=index._name)

        call_command('install_es_indexes')

        # Verify the index was created
        for index in registry.get_indices():
            # pylint: disable=protected-access
            assert self.es.indices.exists(index=index._name)

    def test_alias_exists(self):
        """ Verify the app does not setup a new Elasticsearch index if the alias is already set. """
        # pylint: disable=protected-access
        index_names = [index._name for index in registry.get_indices()]
        for index_name in index_names:
            # Verify the index exists
            assert self.es.indices.exists(index=index_name)

        call_command('install_es_indexes')
        for index_name in index_names:
            # Verify the index still exists
            assert self.es.indices.exists(index=index_name)
