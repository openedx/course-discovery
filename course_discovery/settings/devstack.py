# noinspection PyUnresolvedReferences
from course_discovery.settings._debug_toolbar import *  # isort:skip
from course_discovery.settings.production import *

DEBUG = True

# Docker does not support the syslog socket at /dev/log. Rely on the console.
LOGGING['handlers']['local'] = {
    'class': 'logging.NullHandler',
}

# Determine which requests should render Django Debug Toolbar
INTERNAL_IPS = ('127.0.0.1',)

HAYSTACK_CONNECTIONS['default']['URL'] = 'http://edx.devstack.elasticsearch:9200/'

SOCIAL_AUTH_REDIRECT_IS_HTTPS = False

DEFAULT_PARTNER_ID = 1

# Allow live changes to JS and CSS
COMPRESS_OFFLINE = False
COMPRESS_ENABLED = False

PARLER_LANGUAGES = {
    1: (
        {'code': LANGUAGE_CODE, },
        {'code': 'es', },
    ),
    'default': {
         'fallbacks': [PARLER_DEFAULT_LANGUAGE_CODE],
         'hide_untranslated': False,
     }
 }

#####################################################################
# Lastly, see if the developer has any local overrides.
if os.path.isfile(join(dirname(abspath(__file__)), 'private.py')):
    from .private import *  # pylint: disable=import-error
