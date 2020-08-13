from django.conf import settings
from django.core.management import call_command
from django.test import TestCase

from course_discovery.apps.core.tests.mixins import ElasticsearchTestMixin

LOGGER_NAME = 'courses.management.commands.install_es_indexes'


class InstallEsIndexesCommandTests(ElasticsearchTestMixin, TestCase):
    def setUp(self):
        super().setUp()
        call_command('search_index', '--delete', '-f')

    def test_create_index(self):
        """ Verify the app sets the alias and creates a new index. """
        index_names = settings.ELASTICSEARCH_INDEX_NAMES
        for __, index_name in index_names.items():
            # Delete the index
            self.es.indices.delete(index=index_name, ignore=404)
            self.assertFalse(self.es.indices.exists(index=index_name))

        call_command('search_index', '--create')

        # Verify the index was created
        for __, index_name in index_names.items():
            self.assertTrue(self.es.indices.exists(index=index_name))
