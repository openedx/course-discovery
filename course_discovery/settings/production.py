import warnings
from os import environ

import certifi
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

with open(CONFIG_FILE) as f:
    config_from_yaml = yaml.load(f)

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

HAYSTACK_CONNECTIONS['default'].update({
    'URL': ELASTICSEARCH_URL,
    'INDEX_NAME': ELASTICSEARCH_INDEX_NAME,
    'KWARGS': {
        'verify_certs': True,
        'ca_certs': certifi.where(),
    },
})

for override, value in DB_OVERRIDES.items():
    DATABASES['default'][override] = value

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
