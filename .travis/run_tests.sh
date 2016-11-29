#!/bin/bash -xe
. /edx/app/discovery/venvs/discovery/bin/activate
. /edx/app/discovery/nodeenvs/discovery/bin/activate

apt update
apt install -y xvfb firefox gettext wget

cd
wget https://github.com/mozilla/geckodriver/releases/download/v0.11.1/geckodriver-v0.11.1-linux64.tar.gz
tar xvzf geckodriver-v0.11.1-linux64.tar.gz
mv geckodriver /usr/bin/

pip install --upgrade selenium

cd /edx/app/discovery/discovery
# Make it so bower can run without sudo.
# https://github.com/GeoNode/geonode/pull/1070
echo '{ "allow_root": true }' > /root/.bowerrc

make requirements
make requirements.js
# Ensure documentation can be compiled
cd docs && make html
cd ..

export DJANGO_SETTINGS_MODULE=course_discovery.settings.test

# Check if translation files are up-to-date
make validate_translations

# Compile assets and run validation
make clean_static
make static
xvfb-run make validate
