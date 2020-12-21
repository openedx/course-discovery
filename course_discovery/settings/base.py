import os
import platform
from logging.handlers import SysLogHandler
from os.path import abspath, dirname, join
from sys import path

from corsheaders.defaults import default_headers as corsheaders_default_headers

here = lambda *x: join(abspath(dirname(__file__)), *x)
PROJECT_ROOT = here('..')
root = lambda *x: abspath(join(abspath(PROJECT_ROOT), *x))

path.append(root('apps'))

# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = os.environ.get('COURSE_DISCOVERY_SECRET_KEY', 'insecure-secret-key')

OPENEXCHANGERATES_API_KEY = None

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = False

ALLOWED_HOSTS = []

# Application definition

INSTALLED_APPS = [
    'dal',
    'dal_select2',
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'django.contrib.sites',
]

THIRD_PARTY_APPS = [
    'release_util',
    'rest_framework',
    'rest_framework_swagger',
    'social_django',
    'waffle',
    'sortedm2m',
    'simple_history',
    'guardian',
    'dry_rest_permissions',
    'compressor',
    'django_filters',
    'django_fsm',
    'storages',
    'django_comments',
    'django_sites_extensions',
    'taggit',
    'taggit_autosuggest',
    'taggit_serializer',
    'solo',
    'webpack_loader',
    'parler',
    # edx-drf-extensions
    'csrf.apps.CsrfAppConfig',  # Enables frontend apps to retrieve CSRF tokens.
    'corsheaders',
    'adminsortable2',
    'xss_utils',
    'algoliasearch_django',
    'taxonomy',
]

ALGOLIA = {
    'APPLICATION_ID': '',
    'API_KEY': '',
}

PROJECT_APPS = [
    'course_discovery.apps.core',
    'course_discovery.apps.ietf_language_tags',
    'course_discovery.apps.api',
    'course_discovery.apps.catalogs',
    'course_discovery.apps.course_metadata',
    'course_discovery.apps.edx_haystack_extensions',
    'course_discovery.apps.publisher',
    'course_discovery.apps.publisher_comments',
]


INSTALLED_APPS += THIRD_PARTY_APPS
INSTALLED_APPS += PROJECT_APPS

# NOTE: Haystack must be installed after core so that we can override Haystack's management commands with our own.
INSTALLED_APPS += ['haystack']

MIDDLEWARE = (
    'corsheaders.middleware.CorsMiddleware',
    'edx_django_utils.cache.middleware.RequestCacheMiddleware',
    'edx_rest_framework_extensions.auth.jwt.middleware.JwtAuthCookieMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.locale.LocaleMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.contrib.sites.middleware.CurrentSiteMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
    'social_django.middleware.SocialAuthExceptionMiddleware',
    'waffle.middleware.WaffleMiddleware',
    'simple_history.middleware.HistoryRequestMiddleware',
    'edx_django_utils.cache.middleware.TieredCacheMiddleware',
    'edx_rest_framework_extensions.middleware.RequestMetricsMiddleware',
    'edx_rest_framework_extensions.auth.jwt.middleware.EnsureJWTAuthSettingsMiddleware',
)

ROOT_URLCONF = 'course_discovery.urls'

# Python dotted path to the WSGI application used by Django's runserver.
WSGI_APPLICATION = 'course_discovery.wsgi.application'

# Database
# https://docs.djangoproject.com/en/2.2/ref/settings/#databases
# Set this value in the environment-specific files (e.g. local.py, production.py, test.py)
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.',
        'NAME': 'discovery',
        'USER': 'discov001',
        'PASSWORD': 'password',
        'HOST': 'localhost',  # Empty for localhost through domain sockets or '127.0.0.1' for localhost through TCP.
        'PORT': '',  # Set to empty string for default.
        'ATOMIC_REQUESTS': False,
    },
    'read_replica': {
        'ENGINE': 'django.db.backends.',
        'NAME': 'discovery',
        'USER': 'discov001',
        'PASSWORD': 'password',
        'HOST': 'localhost',
        'PORT': '',
        'ATOMIC_REQUESTS': False,
    },
}

# Internationalization
# See: https://docs.djangoproject.com/en/dev/ref/settings/#language-code
# http://www.i18nguy.com/unicode/language-identifiers.html
LANGUAGE_CODE = 'en'

PARLER_DEFAULT_LANGUAGE_CODE = LANGUAGE_CODE

PARLER_LANGUAGES = {
    1: (
        {'code': LANGUAGE_CODE, },
    ),
    'default': {
         'fallbacks': [PARLER_DEFAULT_LANGUAGE_CODE],
         'hide_untranslated': False,
     }
 }

# Parler seems to be a bit overeager with its caching of translated models,
# and so we get a large number of sets, but rarely any gets
PARLER_ENABLE_CACHING = False

# Determines whether the caching mixin in course_discovery/apps/api/cache.py is used
USE_API_CACHING = True

TIME_ZONE = 'UTC'

USE_I18N = True

USE_L10N = True

USE_TZ = True

LOCALE_PATHS = (
    root('conf', 'locale'),
)


# MEDIA CONFIGURATION
# See: https://docs.djangoproject.com/en/dev/ref/settings/#media-root
MEDIA_ROOT = root('media')

# See: https://docs.djangoproject.com/en/dev/ref/settings/#media-url
MEDIA_URL = '/media/'
# END MEDIA CONFIGURATION


# STATIC FILE CONFIGURATION
# See: https://docs.djangoproject.com/en/dev/ref/settings/#static-root
STATIC_ROOT = root('assets')

# See: https://docs.djangoproject.com/en/dev/ref/settings/#static-url
STATIC_URL = '/static/'

# Is this a dev environment where static files need to be explicitly added to the URL configuration?
STATIC_SERVE_EXPLICITLY = False

# See: https://docs.djangoproject.com/en/dev/ref/contrib/staticfiles/#std:setting-STATICFILES_DIRS
STATICFILES_DIRS = (
    root('static'),
)

STATICFILES_FINDERS = (
    'django.contrib.staticfiles.finders.FileSystemFinder',
    'django.contrib.staticfiles.finders.AppDirectoriesFinder',
    'compressor.finders.CompressorFinder',
)

COMPRESS_PRECOMPILERS = (
    ('text/x-scss', 'django_libsass.SassCompiler'),
)

# Minify CSS
COMPRESS_CSS_FILTERS = [
    'compressor.filters.css_default.CssAbsoluteFilter',
]

WEBPACK_LOADER = {
    'DEFAULT': {
        'BUNDLE_DIR_NAME': 'bundles/',
        'STATS_FILE': root('..', 'webpack-stats.json'),
    }
}

# TEMPLATE CONFIGURATION
# See: https://docs.djangoproject.com/en/1.8/ref/settings/#templates
TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'APP_DIRS': True,
        'DIRS': (
            root('templates'),
        ),
        'OPTIONS': {
            'context_processors': (
                'django.contrib.auth.context_processors.auth',
                'django.template.context_processors.debug',
                'django.template.context_processors.i18n',
                'django.template.context_processors.media',
                'django.template.context_processors.static',
                'django.template.context_processors.tz',
                'django.template.context_processors.request',
                'django.contrib.messages.context_processors.messages',
                'course_discovery.apps.core.context_processors.core',
            ),
            'debug': True,  # Django will only display debug pages if the global DEBUG setting is set to True.
        }
    },
]
# END TEMPLATE CONFIGURATION


# COOKIE CONFIGURATION
# The purpose of customizing the cookie names is to avoid conflicts when
# multiple Django services are running behind the same hostname.
# Detailed information at: https://docs.djangoproject.com/en/dev/ref/settings/
SESSION_COOKIE_NAME = 'course_discovery_sessionid'
CSRF_COOKIE_NAME = 'course_discovery_csrftoken'
LANGUAGE_COOKIE_NAME = 'course_discovery_language'
# END COOKIE CONFIGURATION

# AUTHENTICATION CONFIGURATION
LOGIN_URL = '/login/'
LOGOUT_URL = '/logout/'

AUTH_USER_MODEL = 'core.User'

AUTHENTICATION_BACKENDS = (
    'auth_backends.backends.EdXOAuth2',
    'django.contrib.auth.backends.ModelBackend',
    'guardian.backends.ObjectPermissionBackend',
)

CORS_ALLOW_CREDENTIALS = True
CORS_ALLOW_HEADERS = corsheaders_default_headers + (
    'use-jwt-cookie',
)
# CORS_ORIGIN_WHITELIST is empty by default so above is not used unless the whitelist is set elsewhere

# Guardian settings
ANONYMOUS_USER_NAME = None  # Do not allow anonymous user access
GUARDIAN_MONKEY_PATCH = False  # Use the mixin on the User model instead of monkey-patching.

ENABLE_AUTO_AUTH = False
AUTO_AUTH_USERNAME_PREFIX = 'auto_auth_'

SOCIAL_AUTH_STRATEGY = 'auth_backends.strategies.EdxDjangoStrategy'

# Set these to the correct values for your OAuth2 provider (e.g., devstack)
SOCIAL_AUTH_EDX_OAUTH2_KEY = "discovery-sso-key"
SOCIAL_AUTH_EDX_OAUTH2_SECRET = "discovery-sso-secret"
SOCIAL_AUTH_EDX_OAUTH2_ISSUER = "http://127.0.0.1:8000"
SOCIAL_AUTH_EDX_OAUTH2_URL_ROOT = "http://127.0.0.1:8000"
SOCIAL_AUTH_EDX_OAUTH2_LOGOUT_URL = "http://127.0.0.1:8000/logout"

BACKEND_SERVICE_EDX_OAUTH2_KEY = "discovery-backend-service-key"
BACKEND_SERVICE_EDX_OAUTH2_SECRET = "discovery-backend-service-secret"
BACKEND_SERVICE_EDX_OAUTH2_PROVIDER_URL = "http://127.0.0.1:8000/oauth2"

# OAuth request timeout: either a (connect, read) tuple or a float, in seconds.
OAUTH_API_TIMEOUT = (3.05, 1)

# Request the user's permissions in the ID token
EXTRA_SCOPE = ['permissions']

# TODO Set this to another (non-staff, ideally) path.
LOGIN_REDIRECT_URL = '/admin/'
# END AUTHENTICATION CONFIGURATION


# OPENEDX-SPECIFIC CONFIGURATION
PLATFORM_NAME = 'Your Platform Name Here'
# END OPENEDX-SPECIFIC CONFIGURATION

# Set up logging for development use (logging to stdout)
level = 'DEBUG' if DEBUG else 'INFO'
hostname = platform.node().split(".")[0]

# Use a different address for Mac OS X
syslog_address = '/var/run/syslog' if platform.system().lower() == 'darwin' else '/dev/log'
syslog_format = '[service_variant=discovery][%(name)s] %(levelname)s [{hostname}  %(process)d] ' \
                '[%(pathname)s:%(lineno)d] - %(message)s'.format(hostname=hostname)

LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'standard': {
            'format': '%(asctime)s %(levelname)s %(process)d [%(name)s] %(pathname)s:%(lineno)d - %(message)s',
        },
        'syslog_format': {'format': syslog_format},
    },
    'handlers': {
        'console': {
            'level': level,
            'class': 'logging.StreamHandler',
            'formatter': 'standard',
            'stream': 'ext://sys.stdout',
        },
        'local': {
            'level': level,
            'class': 'logging.handlers.SysLogHandler',
            'address': syslog_address,
            'formatter': 'syslog_format',
            'facility': SysLogHandler.LOG_LOCAL0,
        },
    },
    'loggers': {
        'django': {
            'handlers': ['console', 'local'],
            'propagate': True,
            'level': 'INFO'
        },
        'requests': {
            'handlers': ['console', 'local'],
            'propagate': True,
            'level': 'WARNING'
        },
        'factory': {
            'handlers': ['console', 'local'],
            'propagate': True,
            'level': 'WARNING'
        },
        'elasticsearch': {
            'handlers': ['console', 'local'],
            'propagate': True,
            'level': 'WARNING'
        },
        'urllib3': {
            'handlers': ['console', 'local'],
            'propagate': True,
            'level': 'WARNING'
        },
        'django.request': {
            'handlers': ['console', 'local'],
            'propagate': True,
            'level': 'WARNING'
        },
        '': {
            'handlers': ['console', 'local'],
            'level': 'DEBUG',
            'propagate': False
        },
    }
}

REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': (
        'edx_rest_framework_extensions.auth.jwt.authentication.JwtAuthentication',
        'rest_framework.authentication.SessionAuthentication',
        'rest_framework.authentication.BasicAuthentication',
    ),
    'DEFAULT_PAGINATION_CLASS': 'course_discovery.apps.api.pagination.PageNumberPagination',
    'DEFAULT_PERMISSION_CLASSES': (
        'rest_framework.permissions.DjangoModelPermissions',
    ),
    'PAGE_SIZE': 20,
    'TEST_REQUEST_RENDERER_CLASSES': (
        'rest_framework.renderers.MultiPartRenderer',
        'rest_framework.renderers.JSONRenderer',
        'rest_framework.renderers.BrowsableAPIRenderer',
    ),
    'DEFAULT_THROTTLE_CLASSES': (
        'course_discovery.apps.core.throttles.OverridableUserRateThrottle',
    ),
    'DEFAULT_THROTTLE_RATES': {
        'user': '100/hour',
    },
    'DEFAULT_SCHEMA_CLASS': 'rest_framework.schemas.coreapi.AutoSchema'
}


# http://chibisov.github.io/drf-extensions/docs/
REST_FRAMEWORK_EXTENSIONS = {
    'DEFAULT_CACHE_ERRORS': False,
    'DEFAULT_CACHE_RESPONSE_TIMEOUT': None,
    'DEFAULT_LIST_CACHE_KEY_FUNC': 'course_discovery.apps.api.cache.timestamped_list_key_constructor',
    'DEFAULT_OBJECT_CACHE_KEY_FUNC': 'course_discovery.apps.api.cache.timestamped_object_key_constructor',
}

# NOTE (CCB): JWT_SECRET_KEY is intentionally not set here to avoid production releases with a public value.
# Set a value in a downstream settings file.
JWT_AUTH = {
    'JWT_ALGORITHM': 'HS256',
    'JWT_AUDIENCE': 'course-discovery',
    'JWT_ISSUER': [
        {
            'AUDIENCE': 'SET-ME-PLEASE',
            'ISSUER': 'http://127.0.0.1:8000/oauth2',
            'SECRET_KEY': 'SET-ME-PLEASE'
        }
    ],
    'JWT_DECODE_HANDLER': 'edx_rest_framework_extensions.auth.jwt.decoder.jwt_decode_handler',
    'JWT_VERIFY_AUDIENCE': False,
    'JWT_AUTH_COOKIE': 'edx-jwt-cookie',
    'JWT_PUBLIC_SIGNING_JWK_SET': None,
    'JWT_AUTH_COOKIE_HEADER_PAYLOAD': 'edx-jwt-cookie-header-payload',
    'JWT_AUTH_COOKIE_SIGNATURE': 'edx-jwt-cookie-signature',
    'JWT_AUTH_HEADER_PREFIX': 'JWT',
}

SWAGGER_SETTINGS = {
    'DOC_EXPANSION': 'list',
}

# Elasticsearch uses index settings to specify available analyzers.
# We are adding the lowercase analyzer and tweaking the ngram analyzers here,
# so we need to use these settings rather than the index defaults.
# We are making these changes to enable autocomplete for the typeahead endpoint.
# In addition we are specifying the number of shards and replicas that indices
# will be created with as recommended here:
# https://aws.amazon.com/blogs/database/get-started-with-amazon-elasticsearch-service-how-many-shards-do-i-need/
ELASTICSEARCH_INDEX_SETTINGS = {
    'settings': {
        'index': {
            'number_of_shards': 1,
            'number_of_replicas': 1
        },
        'analysis': {
            'tokenizer': {
                'haystack_edgengram_tokenizer': {
                    'type': 'edgeNGram',
                    'side': 'front',
                    'min_gram': 2,
                    'max_gram': 15
                },
                'haystack_ngram_tokenizer': {
                    'type': 'nGram',
                    'min_gram': 2,
                    'max_gram': 15
                }
            },
            'analyzer': {
                'lowercase': {
                    'type': 'custom',
                    'tokenizer': 'keyword',
                    'filter': [
                        'lowercase',
                        'synonym',
                    ]
                },
                'snowball_with_synonyms': {
                    'type': 'custom',
                    'filter': [
                        'standard',
                        'lowercase',
                        'snowball',
                        'synonym'
                    ],
                    'tokenizer': 'standard'
                },
                'ngram_analyzer': {
                    'type':'custom',
                    'filter': [
                        'lowercase',
                        'haystack_ngram',
                        'synonym',
                    ],
                    'tokenizer': 'keyword'
                }
            },
            'filter': {
                'haystack_ngram': {
                    'type': 'nGram',
                    'min_gram': 2,
                    'max_gram': 22
                },
                'synonym' : {
                  'type': 'synonym',
                  'ignore_case': 'true',
                  'synonyms': []
                }
            }
        }
    }
}

SYNONYMS_MODULE = 'course_discovery.settings.synonyms'

# Haystack configuration (http://django-haystack.readthedocs.io/en/v2.5.0/settings.html)
HAYSTACK_ITERATOR_LOAD_PER_QUERY = 5000

HAYSTACK_CONNECTIONS = {
    'default': {
        'ENGINE': 'course_discovery.apps.edx_haystack_extensions.backends.EdxElasticsearchSearchEngine',
        'URL': 'http://localhost:9200/',
        'INDEX_NAME': 'catalog',
    },
}

# We do not use the RealtimeSignalProcessor here to avoid overloading our
# Elasticsearch instance when running the refresh_course_metadata command
HAYSTACK_SIGNAL_PROCESSOR = 'haystack.signals.BaseSignalProcessor'
HAYSTACK_INDEX_RETENTION_LIMIT = 3

# Update Index Settings
# Make sure the size of the new index does not change by more than this percentage
INDEX_SIZE_CHANGE_THRESHOLD = .1

# Elasticsearch search query facet "size" option to increase from the default value of "100"
# See  https://www.elastic.co/guide/en/elasticsearch/reference/1.5/search-facets-terms-facet.html#_accuracy_control
SEARCH_FACET_LIMIT = 10000

# Precision settings for the elasticsearch cardinality aggregations used to compute distinct hit and facet counts.
# The elasticsearch cardinality aggregation is not guarenteed to produce accurate results. Accuracy is configurable via
# an optional precision_threshold setting. Cardinality aggregations for queries that produce fewer results than the
# precision threshold can be expected to be pretty accurate. Cardinality aggregations for queries that produce more
# results than the precision_threshold will be less accurate. Setting a higher value for precision_threshold requires
# a memory tradeoff of rougly precision_threshold * 8 bytes. See the elasticsearch docs for more details:
# https://www.elastic.co/guide/en/elasticsearch/reference/1.5/search-aggregations-metrics-cardinality-aggregation.html
#
# We use a higher value for hit precision than for facet precision for two reasons:
#   1.) The hit count is more visible to users than the facet counts.
#   2.) The performance penalty for having a higher hit precision is less than the penalty for a higher facet
#       precision, since the hit count only requires a single aggregation.
DISTINCT_COUNTS_HIT_PRECISION = 1500
DISTINCT_COUNTS_FACET_PRECISION = 250

# The number of records that should be requested when warming the SearchQuerySet cache. Set this to equal the
# number of records typically requested with each search query in order to reduce the number of queries that need
# to be executed.
DISTINCT_COUNTS_QUERY_CACHE_WARMING_COUNT = 20

DEFAULT_PARTNER_ID = None

# See: https://docs.djangoproject.com/en/dev/ref/settings/#site-id
# edx-django-sites-extensions will fallback to this site if we cannot identify the site from the hostname.
SITE_ID = 1

TAGGIT_CASE_INSENSITIVE = True

# django-solo configuration (https://github.com/lazybird/django-solo#settings)
SOLO_CACHE = 'default'
SOLO_CACHE_TIMEOUT = 3600

ENABLE_PUBLISHER = False  # either old (publisher djangoapp) or new (frontend-app-publisher)
PUBLISHER_FROM_EMAIL = None

USERNAME_REPLACEMENT_WORKER = "REPLACE WITH VALID USERNAME"

# If no upgrade deadline is specified for a course run seat, when the course is published the deadline will default to
# the course run end date minus the specified number of days.
PUBLISHER_UPGRADE_DEADLINE_DAYS = 10

# Django Debug Toolbar settings
# http://django-debug-toolbar.readthedocs.org/en/latest/installation.html
if os.environ.get('ENABLE_DJANGO_TOOLBAR', False):
    INSTALLED_APPS += [
        'debug_toolbar',
        'elastic_panel',
    ]

    MIDDLEWARE += (
        'debug_toolbar.middleware.DebugToolbarMiddleware',
    )

    DEBUG_TOOLBAR_PATCH_SETTINGS = False

    DEBUG_TOOLBAR_PANELS = [
        'debug_toolbar.panels.versions.VersionsPanel',
        'debug_toolbar.panels.timer.TimerPanel',
        'debug_toolbar.panels.settings.SettingsPanel',
        'debug_toolbar.panels.headers.HeadersPanel',
        'debug_toolbar.panels.request.RequestPanel',
        'debug_toolbar.panels.sql.SQLPanel',
        'debug_toolbar.panels.staticfiles.StaticFilesPanel',
        'debug_toolbar.panels.templates.TemplatesPanel',
        'debug_toolbar.panels.cache.CachePanel',
        'debug_toolbar.panels.signals.SignalsPanel',
        'debug_toolbar.panels.logging.LoggingPanel',
        'debug_toolbar.panels.redirects.RedirectsPanel',
        'elastic_panel.panel.ElasticDebugPanel'
    ]

AWS_SES_REGION_ENDPOINT = "email.us-east-1.amazonaws.com"
AWS_SES_REGION_NAME = "us-east-1"
CORS_ORIGIN_WHITELIST = []
CSRF_COOKIE_SECURE = False
ELASTICSEARCH_INDEX_NAME = "catalog"
ELASTICSEARCH_URL = "http://127.0.0.1:9200/"
EMAIL_BACKEND = "django_ses.SESBackend"
EMAIL_HOST = "localhost"
EMAIL_HOST_PASSWORD = ""
EMAIL_HOST_USER = ""
EMAIL_PORT = 25
EMAIL_USE_TLS = False
EXTRA_APPS = []
SESSION_EXPIRE_AT_BROWSER_CLOSE = False
STATICFILES_STORAGE = "django.contrib.staticfiles.storage.StaticFilesStorage"
CACHES = {
    'default': {
        'BACKEND': 'django.core.cache.backends.locmem.LocMemCache',
    }
}
EDX_DRF_EXTENSIONS = {
    "OAUTH2_USER_INFO_URL": "http://127.0.0.1:8000/oauth2/user_info"
}
API_ROOT = None
MEDIA_STORAGE_BACKEND = {
    'DEFAULT_FILE_STORAGE': 'django.core.files.storage.FileSystemStorage',
    'MEDIA_ROOT': MEDIA_ROOT,
    'MEDIA_URL': MEDIA_URL
}


# Settings related to the taxonomy_support
TAXONOMY_COURSE_METADATA_PROVIDER = 'course_discovery.apps.taxonomy_support.providers.DiscoveryCourseMetadataProvider'

# Settings related to the EMSI client
EMSI_API_ACCESS_TOKEN_URL = 'https://auth.emsicloud.com/connect/token'
EMSI_API_BASE_URL = 'https://emsiservices.com'
EMSI_CLIENT_ID = ''
EMSI_CLIENT_SECRET = ''
