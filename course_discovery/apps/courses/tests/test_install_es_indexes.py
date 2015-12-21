import mock
from django.conf import settings
from django.test import TestCase
from django.core.management import call_command
from elasticsearch import TransportError
from elasticsearch.client import IndicesClient
from testfixtures import LogCapture

from course_discovery.apps.core.tests.mixins import ElasticsearchTestMixin

LOGGER_NAME = 'courses.management.commands.install_es_indexes'


class CourseInstallEsIndexes(ElasticsearchTestMixin, TestCase):
    def test_ready_create_index(self):
        """ Verify the app does not setup a new Elasticsearch index if one exists already. """
        host = settings.ELASTICSEARCH['host']
        index = settings.ELASTICSEARCH['index']

        # Delete the index
        self.es.indices.delete(index=index, ignore=404)  # pylint: disable=unexpected-keyword-arg
        self.assertFalse(self.es.indices.exists(index=index))

        with LogCapture(LOGGER_NAME) as l:
            call_command('install_es_indexes')

            # Verify the index was created
            self.assertTrue(self.es.indices.exists(index=index))

        l.check(
            (LOGGER_NAME, 'INFO',
             'Attempting to establish initial connection to Elasticsearch host [{}]...'.format(host)),
            (LOGGER_NAME, 'INFO', '...success!'),
            (LOGGER_NAME, 'INFO', 'Making sure index [{}] exists...'.format(index)),
            (LOGGER_NAME, 'INFO', '...index created.')
        )

    def test_ready_index_exists(self):
        """ Verify the app does not setup a new Elasticsearch index if one exists already. """
        host = settings.ELASTICSEARCH['host']
        index = settings.ELASTICSEARCH['index']

        # Verify the index exists
        self.assertTrue(self.es.indices.exists(index=index))

        with mock.patch.object(IndicesClient, 'create') as mock_create:
            mock_create.side_effect = TransportError(400)

            with LogCapture(LOGGER_NAME) as l:
                # This call should NOT raise an exception.
                call_command('install_es_indexes')

        # Verify the index still exists
        self.assertTrue(self.es.indices.exists(index=index))

        l.check(
            (LOGGER_NAME, 'INFO',
             'Attempting to establish initial connection to Elasticsearch host [{}]...'.format(host)),
            (LOGGER_NAME, 'INFO', '...success!'),
            (LOGGER_NAME, 'INFO', 'Making sure index [{}] exists...'.format(index)),
            (LOGGER_NAME, 'INFO', '...index already exists.')
        )

    def test_ready_es_failure(self):
        """ Verify Elasticsearch errors are raised if the app fails to create the index. """
        with mock.patch.object(IndicesClient, 'create') as mock_create:
            mock_create.side_effect = TransportError(500)

            with self.assertRaises(TransportError):
                call_command('install_es_indexes')
