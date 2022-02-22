#!/bin/sh

# Examples:
# .ci/run-in-docker.sh make test
# .ci/run-in-docker.sh 'echo hello; echo goodbye'
# .ci/run-in-docker.sh -f script.sh

if [ "$1" = "-f" ]; then
  echo '. /edx/app/discovery/discovery_env
        export DJANGO_SETTINGS_MODULE=course_discovery.settings.test' |
  cat - "$2" |
  exec docker exec --workdir /edx/app/discovery/discovery --env TOXENV --env DB_HOST="$DB_HOST" --interactive discovery sh -s
else
  exec docker exec --workdir /edx/app/discovery/discovery --env TOXENV --env DB_HOST="$DB_HOST" --tty discovery sh -c "
  . /edx/app/discovery/discovery_env
  export DJANGO_SETTINGS_MODULE=course_discovery.settings.test
  $*
  "
fi
