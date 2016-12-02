#!/bin/bash -xe
. /edx/app/discovery/venvs/discovery/bin/activate
cd /edx/app/discovery/discovery
coverage xml
