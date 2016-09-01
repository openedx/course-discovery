from course_discovery.settings.production import *
from course_discovery.settings.shared.debug_toolbar import *

DEBUG = True

# Docker does not support the syslog socket at /dev/log. Rely on the console.
LOGGING['handlers']['local'] = {
    'class': 'logging.NullHandler',
}

INTERNAL_IPS = ('127.0.0.1',)
# END TOOLBAR CONFIGURATION


HAYSTACK_CONNECTIONS = {
    'default': {
        'ENGINE': 'haystack.backends.elasticsearch_backend.ElasticsearchSearchEngine',
        'URL': 'http://es:9200/',
        'INDEX_NAME': 'catalog',
    },
}

#####################################################################
# Lastly, see if the developer has any local overrides.
if os.path.isfile(join(dirname(abspath(__file__)), 'private.py')):
    from .private import *  # pylint: disable=import-error
