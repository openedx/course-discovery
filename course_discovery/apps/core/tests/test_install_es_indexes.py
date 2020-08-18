from django.core.management import call_command
from django.test import TestCase
from django_elasticsearch_dsl.registries import registry

from course_discovery.apps.core.tests.mixins import ElasticsearchTestMixin

LOGGER_NAME = 'courses.management.commands.install_es_indexes'


class InstallEsIndexesCommandTests(ElasticsearchTestMixin, TestCase):

    def test_create_index(self):
        """ Verify the app sets the alias and creates a new index. """
        for index in registry.get_indices():
            # Delete the index
            self.es.indices.delete(index=index._name, ignore=404)
            self.assertFalse(self.es.indices.exists(index=index._name))

        call_command('install_es_indexes')

        # Verify the index was created
        for index in registry.get_indices():
            self.assertTrue(self.es.indices.exists(index=index._name))

    def test_alias_exists(self):
        """ Verify the app does not setup a new Elasticsearch index if the alias is already set. """
        index_names = [index._name for index in registry.get_indices()]
        for index_name in index_names:
            # Verify the index exists
            self.assertTrue(self.es.indices.exists(index=index_name))

        call_command('install_es_indexes')
        for index_name in index_names:
            # Verify the index still exists
            self.assertTrue(self.es.indices.exists(index=index_name))
