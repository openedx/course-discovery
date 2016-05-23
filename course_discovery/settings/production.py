import platform
import sys
from logging.handlers import SysLogHandler
from os import environ

import certifi
import yaml

from course_discovery.settings.base import *
from course_discovery.settings.utils import get_env_setting

DEBUG = False
TEMPLATE_DEBUG = DEBUG

ALLOWED_HOSTS = ['*']

LOGGING['handlers']['local'] = {
    'level': 'INFO',
    'class': 'logging.handlers.SysLogHandler',
    # Use a different address for Mac OS X
    'address': '/var/run/syslog' if sys.platform == "darwin" else '/dev/log',
    'formatter': 'syslog_format',
    'facility': SysLogHandler.LOG_LOCAL0,
}

LOGGING['formatters']['syslog_format'] = {
    format: (
        "[service_variant=course_discovery]"
        "[%(name)s][env:no_env] %(levelname)s "
        "[{hostname}  %(process)d] [%(filename)s:%(lineno)d] "
        "- %(message)s"
    ).format(
        hostname=platform.node().split(".")[0]
    )
}

# Keep track of the names of settings that represent dicts. Instead of overriding the values in base.py,
# the values read from disk should UPDATE the pre-configured dicts.
DICT_UPDATE_KEYS = ('JWT_AUTH',)

CONFIG_FILE = get_env_setting('COURSE_DISCOVERY_CFG')
with open(CONFIG_FILE) as f:
    config_from_yaml = yaml.load(f)

    # Remove the items that should be used to update dicts, and apply them separately rather
    # than pumping them into the local vars.
    dict_updates = {key: config_from_yaml.pop(key, None) for key in DICT_UPDATE_KEYS}

    for key, value in dict_updates.items():
        if value:
            vars()[key].update(value)

    vars().update(config_from_yaml)

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
