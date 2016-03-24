import os

API_GATEWAY_DISCOVERY_ROOT = os.environ.get('API_GATEWAY_DISCOVERY_ROOT')
if not API_GATEWAY_DISCOVERY_ROOT:
    raise RuntimeError('API_GATEWAY_DISCOVERY_ROOT (e.g. https://api.edx.org/discovery/v1) must be supplied!')

DISCOVERY_API_ACCESS_TOKEN = os.environ.get('DISCOVERY_API_ACCESS_TOKEN')
if not DISCOVERY_API_ACCESS_TOKEN:
    raise RuntimeError('DISCOVERY_API_ACCESS_TOKEN must be supplied!')

CATALOG_ID = int(os.environ.get('CATALOG_ID', 1))
COURSE_ID = os.environ.get('COURSE_ID', 'edX/DemoX')
COURSE_RUN_ID = os.environ.get('COURSE_RUN_ID', 'course-v1:edX+DemoX+Demo_Course')
