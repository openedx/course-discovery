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

HAYSTACK_CONNECTIONS = {
    'default': {
        'ENGINE': '',
        'URL': '',
        'INDEX_NAME': '',
    }
}

LOGGING['handlers']['local'] = {
    'class': 'logging.NullHandler',
}
