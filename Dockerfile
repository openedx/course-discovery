# docker build . -t edxops/discovery:devstack-slim

FROM edxops/python:3.5
ENV DJANGO_SETTINGS_MODULE course_discovery.settings.devstack
ENV ENABLE_DJANGO_TOOLBAR 1

WORKDIR /edx/app/discovery/course_discovery

# Iceweasel is the Debian name for Firefox
RUN apt-get update && apt-get install -y \
    iceweasel \
    libxml2-dev \
    libxslt-dev \
    xvfb

COPY .bowerrc /edx/app/discovery/course_discovery/
COPY bower.json /edx/app/discovery/course_discovery/
COPY Makefile /edx/app/discovery/course_discovery/
COPY package.json /edx/app/discovery/course_discovery/
COPY requirements.txt /edx/app/discovery/course_discovery/
COPY requirements/ /edx/app/discovery/course_discovery/requirements/

RUN make requirements requirements.js production-requirements

ADD . /edx/app/discovery/course_discovery/

RUN make static
