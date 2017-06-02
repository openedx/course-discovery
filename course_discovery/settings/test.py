from course_discovery.settings.base import *
# noinspection PyUnresolvedReferences
from course_discovery.settings.shared.test import *

INSTALLED_APPS += [
    'course_discovery.apps.edx_catalog_extensions',
]

ALLOWED_HOSTS = ['*']

DEFAULT_PARTNER_ID = 1

TEST_NON_SERIALIZED_APPS = [
    # Prevents the issue described at https://code.djangoproject.com/ticket/23727.
    'django.contrib.contenttypes',
    # Because of the bug linked above, loading serialized data for this app in a
    # TransactionTestCase with serialized_rollback=True will cause IntegrityErrors
    # on databases that check foreign key constraints (e.g., MySQL, not SQLite).
    # The app's models contain foreign keys referencing content types that no longer
    # exist when serialized data is loaded. This is a variant of the issue described
    # at https://code.djangoproject.com/ticket/10827.
    'django.contrib.auth',
]

JWT_AUTH['JWT_SECRET_KEY'] = 'course-discovery-jwt-secret-key'

LOGGING['handlers']['local'] = {'class': 'logging.NullHandler'}

PUBLISHER_FROM_EMAIL = 'test@example.com'

# Set to 0 to disable edx-django-sites-extensions to retrieve
# the site from cache and risk working with outdated information.
SITE_CACHE_TTL = 0
