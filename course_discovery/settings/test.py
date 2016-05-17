from course_discovery.settings.base import *

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

HAYSTACK_CONNECTIONS = {
    'default': {
        'ENGINE': 'haystack.backends.elasticsearch_backend.ElasticsearchSearchEngine',
        'URL': os.environ.get('TEST_ELASTICSEARCH_URL', 'http://localhost:9200/'),
        'INDEX_NAME': 'catalog_test',
    },
}

JWT_AUTH['JWT_SECRET_KEY'] = 'course-discovery-jwt-secret-key'

EDX_DRF_EXTENSIONS = {
    'OAUTH2_USER_INFO_URL': 'http://example.com/oauth2/user_info',
}
