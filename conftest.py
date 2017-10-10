import logging

import pytest
from django.core.cache import cache
from pytest_django.lazy_django import skip_if_no_django

logger = logging.getLogger(__name__)


@pytest.fixture
def django_cache(request, settings):
    skip_if_no_django()

    xdist_prefix = getattr(request.config, 'slaveinput', {}).get('slaveid')

    if xdist_prefix:
        for name, cache_settings in settings.CACHES.items():
            # Put a prefix like _gw0, _gw1 etc on xdist processes
            cache_settings['KEY_PREFIX'] = xdist_prefix + '_' + cache_settings.get('KEY_PREFIX', '')
            logger.info('Set cache key prefix for [%s] cache to [%s]', name, cache_settings['KEY_PREFIX'])

    yield cache

    cache.clear()
