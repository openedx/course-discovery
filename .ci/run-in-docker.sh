#!/bin/sh

# Examples:
# .ci/run-in-docker.sh make test
# .ci/run-in-docker.sh 'echo hello; echo goodbye'
# .ci/run-in-docker.sh -f script.sh

if [ "$1" = "-f" ]; then
  echo '. /edx/app/discovery/discovery_env
        export DJANGO_SETTINGS_MODULE=course_discovery.settings.test' |
  cat - "$2" |
  exec docker exec -i -w /edx/app/discovery/discovery -e TOXENV discovery sh -s
else
  exec docker exec -t -w /edx/app/discovery/discovery -e TOXENV discovery sh -c "
  . /edx/app/discovery/discovery_env
  export DJANGO_SETTINGS_MODULE=course_discovery.settings.test
  $*
  "
fi
