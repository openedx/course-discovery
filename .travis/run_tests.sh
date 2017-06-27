#!/bin/bash -xe
. /edx/app/discovery/venvs/discovery/bin/activate
. /edx/app/discovery/nodeenvs/discovery/bin/activate

apt update
apt install -y xvfb firefox gettext wget

# TODO: Fix this in the discovery image
# http://askubuntu.com/questions/393638/unicodedecodeerror-ascii-codec-cant-decode-byte-0x-in-position-ordinal-n
export LANG=C.UTF-8

cd /edx/app/discovery/discovery
export PATH=$PATH:$PWD/node_modules/.bin

# Make it so bower can run without sudo.
# https://github.com/GeoNode/geonode/pull/1070
echo '{ "allow_root": true }' > /root/.bowerrc

make requirements
make requirements.js

# Ensure documentation can be compiled
make docs

# Check if translation files are up-to-date
make validate_translations

# Compile assets and run validation
make clean_static
make static
xvfb-run make validate
