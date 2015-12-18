import mock
from django.apps import AppConfig
from django.conf import settings
from django.test import TestCase, override_settings
from elasticsearch import TransportError
from elasticsearch.client import IndicesClient
from testfixtures import LogCapture

from course_discovery.apps.core.tests.mixins import ElasticsearchTestMixin

LOGGER_NAME = 'course_discovery.apps.courses.apps'


class CoursesConfigTests(ElasticsearchTestMixin, TestCase):
    def setUp(self):
        super(CoursesConfigTests, self).setUp()
        self.app_config = AppConfig.create('course_discovery.apps.courses')

    def test_ready_create_index(self):
        """ Verify the app does not setup a new Elasticsearch index if one exists already. """
        host = settings.ELASTICSEARCH['host']
        index = settings.ELASTICSEARCH['index']

        # Delete the index
        self.es.indices.delete(index=index, ignore=404)  # pylint: disable=unexpected-keyword-arg
        self.assertFalse(self.es.indices.exists(index=index))

        with LogCapture(LOGGER_NAME) as l:
            self.app_config.ready()

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
                self.app_config.ready()

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
                self.app_config.ready()

    @override_settings(ELASTICSEARCH={'connect_on_startup': False})
    def test_ready_without_connect_on_startup(self):
        """
        Verify the app does not attempt to connect to Elasticsearch if the connect_on_startup setting is not set.
        """
        with mock.patch.object(IndicesClient, 'create') as mock_create:
            self.app_config.ready()
            mock_create.assert_not_called()
