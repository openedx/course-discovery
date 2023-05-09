import tempfile

from course_discovery.settings.base import *
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

CACHES = {
    'default': {
        'BACKEND': os.environ.get('CACHE_BACKEND', 'django.core.cache.backends.locmem.LocMemCache'),
        'LOCATION': os.environ.get('CACHE_LOCATION', ''),
    },
    'throttling': {
        'BACKEND': 'django.core.cache.backends.locmem.LocMemCache',
        'LOCATION': 'throttling',
    },
}

# Disable the caching mixin for tests
USE_API_CACHING = False

DATABASES = {
    'default': {
        'ENGINE': os.environ.get('DB_ENGINE', 'django.db.backends.sqlite3'),
        'NAME': os.environ.get('DB_NAME', ':memory:'),
        'USER': os.environ.get('DB_USER', ''),
        'PASSWORD': os.environ.get('DB_PASSWORD', ''),
        'HOST': os.environ.get('DB_HOST', ''),
        'PORT': os.environ.get('DB_PORT', ''),
        'CONN_MAX_AGE': int(os.environ.get('CONN_MAX_AGE', 0)),
    },
}

JWT_AUTH['JWT_SECRET_KEY'] = 'course-discovery-jwt-secret-key'

LOGGING['handlers']['local'] = {
    'class': 'logging.NullHandler',
    'level': 'INFO',
}

ENABLE_PUBLISHER = True
PUBLISHER_FROM_EMAIL = 'test@example.com'

LOADER_INGESTION_CONTACT_EMAIL = 'test@example.com'
MARKETING_SERVICE_NAME = 'Publisher'

# Set to 0 to disable edx-django-sites-extensions to retrieve
# the site from cache and risk working with outdated information.
SITE_CACHE_TTL = 0

# Disable throttling during most testing, as it just adds queries
REST_FRAMEWORK['DEFAULT_THROTTLE_CLASSES'] = ()

################################### BEGIN CELERY ###################################

CELERY_TASK_ALWAYS_EAGER = True

CELERY_TASK_IGNORE_RESULT = True

results_dir = tempfile.TemporaryDirectory()
CELERY_RESULT_BACKEND = f'file://{results_dir.name}'

CELERY_BROKER_URL = 'memory://localhost/'

################################### END CELERY ###################################

PRODUCT_API_URL = 'http://www.example.com'

BOOTCAMP_CONTENTFUL_CONTENT_TYPE = 'bootCampPage'

DEGREE_CONTENTFUL_CONTENT_TYPE = 'degreeDetailPage'

CSV_LOADER_TYPE_SOURCE_REQUIRED_FIELDS.update(
    {
        'executive-education-2u': {
            'ext_source': [
                'syllabus', 'redirect_url', 'organic_url', 'external_identifier', 'lead_capture_form_url',
                'certificate_header', 'certificate_text', 'stat1', 'stat1_text', 'stat2', 'stat2_text',
                'frequently_asked_questions', 'reg_close_date', 'reg_close_time', 'variant_id',
            ],
            'dbz_source': [
                'redirect_url', 'organic_url', 'external_identifier',
            ]
        },
        'bootcamp-2u': {
            'ext_source': ['redirect_url', 'organic_url', 'external_identifier']
        }
    }
)

GEAG_API_INGESTION_FIELDS_MAPPING = {
    'title': 'altName, name',
    'number': 'abbreviation',
    'image': 'cardUrl'
}

GETSMARTER_CLIENT_CREDENTIALS = {
    'CLIENT_ID' : 'test_id',
    'CLIENT_SECRET' : 'test_secret',
    'API_URL' : 'https://test-getsmarter.com/api/v1',
    'PROVIDER_URL' : 'https://auth-test.com',
    'PRODUCTS_DETAILS_URL' : 'https://test-getsmarter.com/api/v1/products?detail=2',
}

DEFAULT_PRODUCT_SOURCE_SLUG = 'test-source'

INGESTION_ARCHIVAL_FLOW_SOURCE_TYPE_CONFIG = {
    'no-archive-source-slug': ['executive-education-2u']
}
