#!/usr/bin/env python

"""
Django administration utility.
"""

import os
import sys

if __name__ == "__main__":
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "course_discovery.settings.local")

    from django.conf import settings
    from django.core.management import execute_from_command_line

    monitoring_enabled = getattr(settings, "ENABLE_CUSTOM_MANAGEMENT_COMMAND_MONITORING", False)

    if monitoring_enabled and len(sys.argv) > 1:
        from course_discovery.apps.core.utils import monitor_django_management_command

        with monitor_django_management_command(sys.argv[1]):
            execute_from_command_line(sys.argv)
    else:
        execute_from_command_line(sys.argv)
