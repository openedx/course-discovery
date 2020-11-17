#!/bin/sh
set -e

# Designed to be run inside the CI container

make requirements

make docs
make clean_static
make static

make quality
make check_keywords
