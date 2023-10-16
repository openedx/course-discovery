#!/bin/sh
set -e

# Designed to be run inside the CI container

apt-get update
apt-get install -y --no-install-recommends firefox gettext
if [ "$TOXENV" == "py38-django42" ]
then
    make requirements_dj42
else
    make requirements
fi
make test
