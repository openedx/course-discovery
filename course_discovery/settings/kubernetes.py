"""
Specific overrides to the base prod settings for a docker production deployment.
"""

import platform
import sys
from .production import *  # pylint: disable=wildcard-import, unused-wildcard-import


def get_docker_logger_config():
    """
    Return the appropriate logging config dictionary. You should assign the
    result of this to the LOGGING var in your settings.
    """

    hostname = platform.node().split(".")[0]
    syslog_format = '[service_variant=discovery][%(name)s] %(levelname)s [{hostname}  %(process)d] ' \
                    '[%(pathname)s:%(lineno)d] - %(message)s'.format(hostname=hostname)

    handlers = ['console']

    logger_config = {
        'version': 1,
        'disable_existing_loggers': False,
        'formatters': {
            'standard': {
                'format': '%(asctime)s %(levelname)s %(process)d '
                          '[%(name)s] %(filename)s:%(lineno)d - %(message)s',
            },
            'syslog_format': {'format': syslog_format},
            'raw': {'format': '%(message)s'},
        },
        'handlers': {
            'console': {
                'level': 'INFO',
                'class': 'logging.StreamHandler',
                'formatter': 'standard',
                'stream': sys.stdout,
            },
        },
        'loggers': {
            'django': {
                'handlers': handlers,
                'propagate': True,
                'level': 'INFO'
            },
            'requests': {
                'handlers': handlers,
                'propagate': True,
                'level': 'WARNING'
            },
            'factory': {
                'handlers': handlers,
                'propagate': True,
                'level': 'WARNING'
            },
            'django.request': {
                'handlers': handlers,
                'propagate': True,
                'level': 'WARNING'
            },
            '': {
                'handlers': handlers,
                'level': 'DEBUG',
                'propagate': False
            },
        }
    }

    return logger_config

LOGGING = get_docker_logger_config()
