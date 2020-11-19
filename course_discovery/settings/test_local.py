import sys

from course_discovery.settings.test import *

# This allows you to use the --reuse-db option, even with in-memory SQLite databases,
# since /dev/shm is a filesystem on the machine's RAM, and should persist between
# processes until you reboot.  Don't use this in CI.
# Source: http://www.obeythetestinggoat.com/speeding-up-django-unit-tests-with-sqlite-keepdb-and-devshm.html
DATABASES['default']['NAME'] = '/dev/shm/course_discovery.test.db.sqlite3'
DATABASES['default']['TEST'] = {'NAME': DATABASES['default']['NAME']}
