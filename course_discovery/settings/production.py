import warnings
from copy import deepcopy
from os import environ

import certifi
import memcache
import MySQLdb
import yaml

from course_discovery.settings.base import *

DEBUG = False
TEMPLATE_DEBUG = DEBUG

ALLOWED_HOSTS = ['*']

LOGGING['handlers']['local']['level'] = 'INFO'

# Keep track of the names of settings that represent dicts. Instead of overriding the values in base.py,
# the values read from disk should UPDATE the pre-configured dicts.
DICT_UPDATE_KEYS = ('JWT_AUTH',)

# This may be overridden by the YAML in DISCOVERY_CFG, but it should be here as a default.
MEDIA_STORAGE_BACKEND = {}

# TODO Drop the try-except block once https://github.com/edx/configuration/pull/3549 is merged and we are using the
# common play for this service.
try:
    CONFIG_FILE = environ['DISCOVERY_CFG']
except KeyError:
    CONFIG_FILE = environ['COURSE_DISCOVERY_CFG']

with open(CONFIG_FILE, encoding='utf-8') as f:
    config_from_yaml = yaml.safe_load(f)

    # Remove the items that should be used to update dicts, and apply them separately rather
    # than pumping them into the local vars.
    dict_updates = {key: config_from_yaml.pop(key, None) for key in DICT_UPDATE_KEYS}

    for key, value in dict_updates.items():
        if value:
            vars()[key].update(value)

    vars().update(config_from_yaml)

    # Unpack media storage settings.
    # It's important we unpack here because of https://github.com/edx/configuration/pull/3307
    vars().update(MEDIA_STORAGE_BACKEND)

# Reset our cache when memcache versions change
CACHES['default']['KEY_PREFIX'] = CACHES['default'].get('KEY_PREFIX', '') + '_' + memcache.__version__

if 'EXTRA_APPS' in locals():
    INSTALLED_APPS += EXTRA_APPS

DB_OVERRIDES = dict(
    PASSWORD=environ.get('DB_MIGRATION_PASS', DATABASES['default']['PASSWORD']),
    ENGINE=environ.get('DB_MIGRATION_ENGINE', DATABASES['default']['ENGINE']),
    USER=environ.get('DB_MIGRATION_USER', DATABASES['default']['USER']),
    NAME=environ.get('DB_MIGRATION_NAME', DATABASES['default']['NAME']),
    HOST=environ.get('DB_MIGRATION_HOST', DATABASES['default']['HOST']),
    PORT=environ.get('DB_MIGRATION_PORT', DATABASES['default']['PORT']),
)

# To attach certifi elasticsearch host you should  do pip install certifi
# should do the trick. elasticsearch-py will automatically look it up.
ELASTICSEARCH_DSL['default'].update({
    'hosts': ELASTICSEARCH_CLUSTER_URL,
})

for override, value in DB_OVERRIDES.items():
    DATABASES['default'][override] = value

if 'read_replica' not in DATABASES:
    DATABASES['read_replica'] = deepcopy(DATABASES['default'])

# NOTE (CCB): Treat all MySQL warnings as exceptions. This is especially
# desired for truncation warnings, which hide potential data integrity issues.
warnings.filterwarnings('error', category=MySQLdb.Warning)

# Minify CSS
COMPRESS_CSS_FILTERS += [
    'compressor.filters.cssmin.CSSMinFilter',
]

# Enable offline compression of CSS/JS
COMPRESS_ENABLED = True
COMPRESS_OFFLINE = True

# Have images and such that we upload be publicly readable
AWS_DEFAULT_ACL = 'public-read'
