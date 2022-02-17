# The bare minimum needed for Sphinx to import each file and generate documentation.

from course_discovery.settings.base import *

DATABASES = {
    'default': {
        'ENGINE': '',
        'NAME': '',
        'USER': '',
        'PASSWORD': '',
        'HOST': '',
        'PORT': '',
    }
}

SECRET_KEY = 'secret'

STATIC_URL = '/static/'

ELASTICSEARCH_DSL = {'default': {'hosts': ''}}
ELASTICSEARCH_INDEX_NAMES = {
    'course_discovery.apps.course_metadata.search_indexes.documents.course': '',
    'course_discovery.apps.course_metadata.search_indexes.documents.course_run': '',
    'course_discovery.apps.course_metadata.search_indexes.documents.learner_pathway': '',
    'course_discovery.apps.course_metadata.search_indexes.documents.person': '',
    'course_discovery.apps.course_metadata.search_indexes.documents.program': '',
}

LOGGING['handlers']['local'] = {
    'class': 'logging.NullHandler',
}
