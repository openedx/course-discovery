import os

API_GATEWAY_CATALOG_ROOT = os.environ.get('API_GATEWAY_CATALOG_ROOT')
if not API_GATEWAY_CATALOG_ROOT:
    raise RuntimeError('API_GATEWAY_CATALOG_ROOT (e.g. https://api.stage.edx.org/catalog/v1) must be supplied!')

API_ACCESS_TOKEN = os.environ.get('API_ACCESS_TOKEN')
if not API_ACCESS_TOKEN:
    raise RuntimeError('API_ACCESS_TOKEN must be supplied!')

CATALOG_ID = int(os.environ.get('CATALOG_ID', 1))
COURSE_ID = os.environ.get('COURSE_ID', 'edX/DemoX')
COURSE_RUN_ID = os.environ.get('COURSE_RUN_ID', 'course-v1:edX+DemoX+Demo_Course')

MARKETING_SITE_URL_ROOT = os.environ.get('MARKETING_SITE_URL_ROOT', 'https://stage.edx.org')
LMS_URL_ROOT = os.environ.get('LMS_URL_ROOT', 'https://courses.stage.edx.org')
ECOMMERCE_URL_ROOT = os.environ.get('ECOMMERCE_URL_ROOT', 'https://ecommerce.stage.edx.org')

BASIC_AUTH_USERNAME = os.environ.get('BASIC_AUTH_USERNAME', '')
BASIC_AUTH_PASSWORD = os.environ.get('BASIC_AUTH_PASSWORD', '')

AFFILIATE_COOKIE_NAME = os.environ.get('AFFILIATE_COOKIE_NAME', 'stage.edx.affiliate_id')
COOKIE_DOMAIN = os.environ.get('COOKIE_DOMAIN', '.edx.org')
