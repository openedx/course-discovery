from django.conf import settings
from django.core.management import call_command
from django.test import TestCase

from course_discovery.apps.core.tests.mixins import ElasticsearchTestMixin

LOGGER_NAME = 'courses.management.commands.install_es_indexes'


class InstallEsIndexesCommandTests(ElasticsearchTestMixin, TestCase):
    def test_create_index(self):
        """ Verify the app sets the alias and creates a new index. """
        index = settings.HAYSTACK_CONNECTIONS['default']['INDEX_NAME']

        # Delete the index
        self.es.indices.delete(index=index, ignore=404)
        self.assertFalse(self.es.indices.exists(index=index))

        call_command('install_es_indexes')

        # Verify the index was created
        self.assertTrue(self.es.indices.exists(index=index))

    def test_alias_exists(self):
        """ Verify the app does not setup a new Elasticsearch index if the alias is already set. """
        index = settings.HAYSTACK_CONNECTIONS['default']['INDEX_NAME']

        # Verify the index exists
        self.assertTrue(self.es.indices.exists(index=index))

        call_command('install_es_indexes')

        # Verify the index still exists
        self.assertTrue(self.es.indices.exists(index=index))
