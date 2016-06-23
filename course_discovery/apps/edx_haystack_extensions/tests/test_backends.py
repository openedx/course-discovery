from django.test import TestCase

from course_discovery.apps.edx_haystack_extensions.backends import EdxElasticsearchSearchBackend
from course_discovery.apps.edx_haystack_extensions.tests.mixins import (
    SimpleQuerySearchBackendMixinTestMixin, NonClearingSearchBackendMixinTestMixin
)


class EdxElasticsearchSearchBackendTests(NonClearingSearchBackendMixinTestMixin, SimpleQuerySearchBackendMixinTestMixin,
                                         TestCase):
    """ Tests for EdxElasticsearchSearchBackend.  """
    backend_class = EdxElasticsearchSearchBackend
