import logging

import pytest
from django.conf import settings
from django.contrib.sites.models import Site
from django.core.cache import cache, caches
from django.core.management import call_command
from django.test.client import Client
from django_elasticsearch_dsl.registries import registry
from elasticsearch_dsl.connections import get_connection
from pytest_django.lazy_django import skip_if_no_django
from xdist.scheduler import LoadScopeScheduling

from course_discovery.apps.core.tests.factories import PartnerFactory, SiteFactory

logger = logging.getLogger(__name__)

TEST_DOMAIN = 'testserver.fake'

# List of test classes that are backed by TransactionTestCase
TTC = ['course_discovery/apps/course_metadata/tests/test_admin.py::ProgramAdminFunctionalTests',
       'course_discovery/apps/course_metadata/management/commands/tests/test_refresh_course_metadata.py::'
       'RefreshCourseMetadataCommandTests']
class LoadScopeSchedulingDjangoOrdered(LoadScopeScheduling):
    def _assign_work_unit(self, node) -> None:
        if not hasattr(self, 'django_ordered'):
            self.django_ordered = True
            for test_class in TTC:
                if test_class in self.workqueue:
                    self.workqueue.move_to_end(test_class)

        return super()._assign_work_unit(node)


@pytest.fixture(scope='session', autouse=True)
def django_cache_add_xdist_key_prefix(request):
    skip_if_no_django()

    xdist_prefix = getattr(request.config, 'workerinput', {}).get('workerid')

    if xdist_prefix:
        # Put a prefix like gw0_, gw1_ etc on xdist processes
        for existing_cache in caches.all():
            existing_cache.key_prefix = xdist_prefix + '_' + existing_cache.key_prefix
            existing_cache.clear()
            logger.info('Set existing cache key prefix to [%s]', existing_cache.key_prefix)

        for name, cache_settings in settings.CACHES.items():
            cache_settings['KEY_PREFIX'] = xdist_prefix + '_' + cache_settings.get('KEY_PREFIX', '')
            logger.info('Set cache key prefix for [%s] cache to [%s]', name, cache_settings['KEY_PREFIX'])


@pytest.fixture
def django_cache(django_cache_add_xdist_key_prefix):  # pylint: disable=redefined-outer-name,unused-argument
    skip_if_no_django()
    yield cache


@pytest.fixture(scope='session', autouse=True)
def elasticsearch_dsl_add_xdist_suffix_to_index_name(request):
    skip_if_no_django()

    xdist_suffix = getattr(request.config, 'workerinput', {}).get('workerid')
    if xdist_suffix:
        # Put a prefix like _gw0, _gw1 etc on xdist processes
        # pylint: disable=protected-access
        for index, document in registry._indices.items():
            name = f'{index._name}_{xdist_suffix}'
            index._name = name
            logger.info('Set index name for elastic connection [%s]', name)

        # Update setting indexes names
        index_names_orig = settings.ELASTICSEARCH_INDEX_NAMES
        index_names = index_names_orig.copy()
        for document, name in index_names.items():
            name = f'{name}_{xdist_suffix}'
            index_names_orig[document] = name


@pytest.fixture
def elasticsearch_dsl_default_connection(
    elasticsearch_dsl_add_xdist_suffix_to_index_name
):  # pylint: disable=redefined-outer-name,unused-argument
    skip_if_no_django()
    esdsl_conn = get_connection()

    call_command('search_index', '--delete', '-f')
    call_command('search_index', '--create')

    yield esdsl_conn


@pytest.fixture
def site(db):  # pylint: disable=unused-argument
    skip_if_no_django()

    Site.objects.all().delete()
    return SiteFactory(id=settings.SITE_ID, domain=TEST_DOMAIN)


@pytest.fixture
def partner(db, site):  # pylint: disable=redefined-outer-name,unused-argument
    skip_if_no_django()
    return PartnerFactory(site=site)


@pytest.fixture
def client():
    skip_if_no_django()

    return Client(SERVER_NAME=TEST_DOMAIN)


@pytest.fixture(autouse=True)
def clear_caches(request):
    for existing_cache in caches.all():
        existing_cache.clear()


@pytest.fixture(scope='session', autouse=True)
def clear_es_indexes():
    yield None
    conn = get_connection()
    for index_name in settings.ELASTICSEARCH_INDEX_NAMES.values():
        conn.indices.delete(index=index_name + '_*')

def pytest_xdist_make_scheduler(config, log):
  return LoadScopeSchedulingDjangofied(config, log)
