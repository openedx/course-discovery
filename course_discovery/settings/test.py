from course_discovery.settings.base import *
# noinspection PyUnresolvedReferences
from course_discovery.settings.shared.test import *

INSTALLED_APPS += [
    'django_nose',
    'course_discovery.apps.edx_catalog_extensions',
]

# IN-MEMORY TEST DATABASE
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': ':memory:',
        'USER': '',
        'PASSWORD': '',
        'HOST': '',
        'PORT': '',
    },
}
# END IN-MEMORY TEST DATABASE

JWT_AUTH['JWT_SECRET_KEY'] = 'course-discovery-jwt-secret-key'

LOGGING['handlers']['local'] = {'class': 'logging.NullHandler'}

REST_FRAMEWORK_EXTENSIONS['DEFAULT_CACHE_RESPONSE_TIMEOUT'] = 0
