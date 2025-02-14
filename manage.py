#!/usr/bin/env python

"""
Django administration utility.
"""

import os
import sys

if __name__ == "__main__":
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "course_discovery.settings.local")

    from django.core.management import execute_from_command_line
    from edx_django_utils.monitoring import monitor_django_management_command

    with monitor_django_management_command(sys.argv[1]):
        execute_from_command_line(sys.argv)
