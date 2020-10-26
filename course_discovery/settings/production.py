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

CONFIG_FILE = environ['DISCOVERY_CFG']
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

if 'read_replica' not in DATABASES:
    DATABASES['read_replica'] = deepcopy(DATABASES['default'])

DB_OVERRIDES = dict(
    DB_MIGRATION_PASS='PASSWORD',
    DB_MIGRATION_ENGINE='ENGINE',
    DB_MIGRATION_USER='USER',
    DB_MIGRATION_NAME='NAME',
    DB_MIGRATION_HOST='HOST',
    DB_MIGRATION_PORT='PORT',
)
for override, db_key in DB_OVERRIDES.items():
    if override in environ:
        DATABASES['default'][db_key] = environ.get(override)
        DATABASES['read_replica'][db_key] = environ.get(override)

HAYSTACK_CONNECTIONS['default'].update({
    'URL': ELASTICSEARCH_URL,
    'INDEX_NAME': ELASTICSEARCH_INDEX_NAME,
    'KWARGS': {
        'verify_certs': True,
        'ca_certs': certifi.where(),
    },
})

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
