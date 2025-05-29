import logging

import pytest
from django.contrib.sites.models import Site
from django.core.cache import cache
from django.test.client import Client
from pytest_django.lazy_django import skip_if_no_django

from course_discovery.apps.core.tests.factories import PartnerFactory, SiteFactory


logger = logging.getLogger(__name__)

TEST_DOMAIN = 'testserver.fake'


@pytest.fixture(scope='session', autouse=True)
def django_cache_add_xdist_key_prefix(request):
    skip_if_no_django()

    from django.conf import settings

    xdist_prefix = getattr(request.config, 'slaveinput', {}).get('slaveid')

    if xdist_prefix:
        # Put a prefix like gw0_, gw1_ etc on xdist processes
        for name, cache_settings in settings.CACHES.items():
            cache_settings['KEY_PREFIX'] = xdist_prefix + '_' + cache_settings.get('KEY_PREFIX', '')
            logger.info('Set cache key prefix for [%s] cache to [%s]', name, cache_settings['KEY_PREFIX'])


@pytest.fixture
def django_cache(django_cache_add_xdist_key_prefix):  # pylint: disable=redefined-outer-name,unused-argument
    skip_if_no_django()
    cache.clear()

    yield cache

    cache.clear()


@pytest.fixture
def site(db):  # pylint: disable=unused-argument
    skip_if_no_django()

    from django.conf import settings

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
