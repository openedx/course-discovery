from django.conf import settings
from django.core.management import call_command
from django.test import TestCase
from elasticsearch import Elasticsearch
from freezegun import freeze_time

from course_discovery.apps.edx_haystack_extensions.tests.mixins import SearchIndexTestMixin


class UpdateIndexTests(SearchIndexTestMixin, TestCase):
    @freeze_time('2016-06-21')
    def test_handle(self):
        """ Verify the command creates a timestamped index and repoints the alias. """
        call_command('update_index')

        alias = settings.HAYSTACK_CONNECTIONS['default']['INDEX_NAME']
        index = '{alias}_20160621_000000'.format(alias=alias)

        host = settings.HAYSTACK_CONNECTIONS['default']['URL']
        connection = Elasticsearch(host)
        response = connection.indices.get_alias(name=alias)
        expected = {
            index: {
                'aliases': {
                    alias: {}
                }
            }
        }
        self.assertDictEqual(response, expected)
