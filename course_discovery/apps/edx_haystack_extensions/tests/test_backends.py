import haystack
from django.test import TestCase

from course_discovery.apps.edx_haystack_extensions.backends import EdxElasticsearchSearchBackend
from course_discovery.apps.edx_haystack_extensions.tests.mixins import (
    NonClearingSearchBackendMixinTestMixin, SimpleQuerySearchBackendMixinTestMixin
)


class EdxElasticsearchSearchBackendTests(NonClearingSearchBackendMixinTestMixin, SimpleQuerySearchBackendMixinTestMixin,
                                         TestCase):
    """ Tests for EdxElasticsearchSearchBackend.  """
    backend_class = EdxElasticsearchSearchBackend

    def test_build_schema_handles_aggregation_key(self):
        """Verify that build_schema marks the aggregation_key field as not_analyzed."""
        backend = self.get_backend()
        index = haystack.connections[backend.connection_alias].get_unified_index()
        fields = index.all_searchfields()
        mapping = backend.build_schema(fields)[1]
        assert mapping.get('aggregation_key')
        assert mapping['aggregation_key']['index'] == 'not_analyzed'
        assert 'analyzer' not in mapping['aggregation_key']
