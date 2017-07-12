import os
import platform
from logging.handlers import SysLogHandler
from os.path import abspath, dirname, join
from sys import path

here = lambda *x: join(abspath(dirname(__file__)), *x)
PROJECT_ROOT = here("..")
root = lambda *x: join(abspath(PROJECT_ROOT), *x)

path.append(root('apps'))

# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = os.environ.get('COURSE_DISCOVERY_SECRET_KEY', 'insecure-secret-key')

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
    'taggit',
    'taggit_autosuggest',
    'taggit_serializer',
    'solo',
]

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

MIDDLEWARE_CLASSES = (
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.locale.LocaleMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.auth.middleware.SessionAuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
    'social_django.middleware.SocialAuthExceptionMiddleware',
    'waffle.middleware.WaffleMiddleware',
    'simple_history.middleware.HistoryRequestMiddleware',
)

ROOT_URLCONF = 'course_discovery.urls'

# Python dotted path to the WSGI application used by Django's runserver.
WSGI_APPLICATION = 'course_discovery.wsgi.application'

# Database
# https://docs.djangoproject.com/en/1.8/ref/settings/#databases
# Set this value in the environment-specific files (e.g. local.py, production.py, test.py)
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.',
        'NAME': '',
        'USER': '',
        'PASSWORD': '',
        'HOST': '',  # Empty for localhost through domain sockets or '127.0.0.1' for localhost through TCP.
        'PORT': '',  # Set to empty string for default.
    }
}

# Internationalization
# https://docs.djangoproject.com/en/dev/topics/i18n/

LANGUAGE_CODE = 'en-us'

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
                'course_discovery.apps.publisher.context_processors.publisher',
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
    'auth_backends.backends.EdXOpenIdConnect',
    'django.contrib.auth.backends.ModelBackend',
    'guardian.backends.ObjectPermissionBackend',
)

# Guardian settings
ANONYMOUS_USER_NAME = None  # Do not allow anonymous user access
GUARDIAN_MONKEY_PATCH = False  # Use the mixin on the User model instead of monkey-patching.

ENABLE_AUTO_AUTH = False
AUTO_AUTH_USERNAME_PREFIX = 'auto_auth_'

SOCIAL_AUTH_STRATEGY = 'auth_backends.strategies.EdxDjangoStrategy'

# Set these to the correct values for your OAuth2/OpenID Connect provider (e.g., devstack)
SOCIAL_AUTH_EDX_OIDC_KEY = 'replace-me'
SOCIAL_AUTH_EDX_OIDC_SECRET = 'replace-me'
SOCIAL_AUTH_EDX_OIDC_URL_ROOT = 'replace-me'
SOCIAL_AUTH_EDX_OIDC_LOGOUT_URL = 'replace-me'
SOCIAL_AUTH_EDX_OIDC_ID_TOKEN_DECRYPTION_KEY = SOCIAL_AUTH_EDX_OIDC_SECRET

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
        'rest_framework.authentication.SessionAuthentication',
        'edx_rest_framework_extensions.authentication.BearerAuthentication',
        'edx_rest_framework_extensions.authentication.JwtAuthentication',
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
    'JWT_ISSUER': 'course-discovery',
    'JWT_DECODE_HANDLER': 'edx_rest_framework_extensions.utils.jwt_decode_handler',
    'JWT_VERIFY_AUDIENCE': False,
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
SITE_ID = 1
COMMENTS_APP = 'course_discovery.apps.publisher_comments'

TAGGIT_CASE_INSENSITIVE = True

# django-solo configuration (https://github.com/lazybird/django-solo#settings)
SOLO_CACHE = 'default'
SOLO_CACHE_TIMEOUT = 3600

PUBLISHER_FROM_EMAIL = None

# Django Debug Toolbar settings
# http://django-debug-toolbar.readthedocs.org/en/latest/installation.html
if os.environ.get('ENABLE_DJANGO_TOOLBAR', False):
    INSTALLED_APPS += [
        'debug_toolbar',
        'elastic_panel',
    ]

    MIDDLEWARE_CLASSES += (
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
