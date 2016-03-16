import os
from au_amber.settings.base import *

# TEST SETTINGS
INSTALLED_APPS += (
    'django_nose',
)

TEST_RUNNER = 'django_nose.NoseTestSuiteRunner'

NOSE_ARGS = [
    '--with-ignore-docstrings',
    '--logging-level=DEBUG',
    '--logging-clear-handlers',
]

# END TEST SETTINGS


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

ELASTICSEARCH = {
    'host': os.environ.get('TEST_ELASTICSEARCH_HOST', 'localhost'),
    'index': 'au_amber_test',
}

JWT_AUTH['JWT_SECRET_KEY'] = 'course-discovery-jwt-secret-key'
