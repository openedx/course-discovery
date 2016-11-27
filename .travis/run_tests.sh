#!/bin/bash -xe
. /edx/app/discovery/venvs/discovery/bin/activate
. /edx/app/discovery/nodeenvs/discovery/bin/activate

apt update
apt install -y xvfb firefox gettext

cd /edx/app/discovery/discovery
pip install -U pip wheel
# Make it so bower can run without sudo.
# https://github.com/GeoNode/geonode/pull/1070
echo '{ "allow_root": true }' > /root/.bowerrc

make requirements
# Ensure documentation can be compiled
cd docs && make html
cd ..

export DJANGO_SETTINGS_MODULE=course_discovery.settings.test

# Check if translation files are up-to-date
make validate_translations

# Compile assets and run validation
xvfb-run make clean_static
xvfb-run make static
xvfb-run make validate_python
xvfb-run make validate_js
