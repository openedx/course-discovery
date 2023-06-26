#!/bin/sh
set -e

# Designed to be run inside the CI container

make requirements

semgrep ci --config p/django
