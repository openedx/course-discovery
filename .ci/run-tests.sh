#!/bin/sh
set -e

# Designed to be run inside the CI container

apt-get update
apt-get install -y --no-install-recommends firefox gettext
make requirements

make test
coverage xml
