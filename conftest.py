import logging

import pytest
from django.conf import settings
from django.contrib.sites.models import Site
from django.core.cache import cache, caches
from django.test.client import Client
from haystack import connections as haystack_connections
from pytest_django.lazy_django import skip_if_no_django

from course_discovery.apps.core.tests.factories import PartnerFactory, SiteFactory
from course_discovery.apps.core.utils import ElasticsearchUtils

logger = logging.getLogger(__name__)

TEST_DOMAIN = 'testserver.fake'


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
def haystack_add_xdist_suffix_to_index_name(request):
    skip_if_no_django()

    xdist_suffix = getattr(request.config, 'workerinput', {}).get('workerid')

    if xdist_suffix:
        # Put a prefix like _gw0, _gw1 etc on xdist processes
        for name, connection in settings.HAYSTACK_CONNECTIONS.items():
            connection['INDEX_NAME'] = connection['INDEX_NAME'] + '_' + xdist_suffix
            logger.info('Set index name for Haystack connection [%s] to [%s]', name, connection['INDEX_NAME'])


@pytest.fixture
def haystack_default_connection(haystack_add_xdist_suffix_to_index_name):  # pylint: disable=redefined-outer-name,unused-argument
    skip_if_no_django()

    backend = haystack_connections['default'].get_backend()

    # Force Haystack to update the mapping for the index
    backend.setup_complete = False

    es = backend.conn
    index_name = backend.index_name
    ElasticsearchUtils.delete_index(es, index_name)
    ElasticsearchUtils.create_alias_and_index(es, index_name)
    ElasticsearchUtils.refresh_index(es, index_name)

    yield backend

    ElasticsearchUtils.delete_index(es, index_name)


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
