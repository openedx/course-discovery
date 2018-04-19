from course_discovery.settings.devstack import *

# noinspection PyUnresolvedReferences
from course_discovery.settings.shared.test import *     # isort:skip

JWT_AUTH['JWT_SECRET_KEY'] = 'course-discovery-jwt-secret-key'

LOGGING['handlers']['local'] = {'class': 'logging.NullHandler'}
