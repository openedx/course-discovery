from course_discovery.settings.base import *
# noinspection PyUnresolvedReferences
from course_discovery.settings.shared.test import *  # isort:skip

INSTALLED_APPS += [
    'course_discovery.apps.edx_catalog_extensions',
]

JWT_AUTH['JWT_SECRET_KEY'] = 'course-discovery-jwt-secret-key'

LOGGING['handlers']['local'] = {'class': 'logging.NullHandler'}
