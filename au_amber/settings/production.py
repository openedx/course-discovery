import platform
import sys
from os import environ

import yaml
from logging.handlers import SysLogHandler

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

CONFIG_FILE = get_env_setting('COURSE_DISCOVERY_CFG')
with open(CONFIG_FILE) as f:
    config_from_yaml = yaml.load(f)
    vars().update(config_from_yaml)

DB_OVERRIDES = dict(
    PASSWORD=environ.get('DB_MIGRATION_PASS', DATABASES['default']['PASSWORD']),
    ENGINE=environ.get('DB_MIGRATION_ENGINE', DATABASES['default']['ENGINE']),
    USER=environ.get('DB_MIGRATION_USER', DATABASES['default']['USER']),
    NAME=environ.get('DB_MIGRATION_NAME', DATABASES['default']['NAME']),
    HOST=environ.get('DB_MIGRATION_HOST', DATABASES['default']['HOST']),
    PORT=environ.get('DB_MIGRATION_PORT', DATABASES['default']['PORT']),
)

ES_OVERRIDES = dict(
    HOST=environ.get('ES_HOST', ELASTICSEARCH['host']),
    INDEX=environ.get('ES_INDEX', ELASTICSEARCH['index']),
)


for override, value in DB_OVERRIDES.items():
    DATABASES['default'][override] = value
