FROM ubuntu:focal as app

ARG PYTHON_VERSION=3.8

ENV DEBIAN_FRONTEND noninteractive
# System requirements.
RUN apt-get update && \
  apt-get install -y software-properties-common && \
  apt-add-repository -y ppa:deadsnakes/ppa && \
  apt-get install -qy \
  curl \
  gettext \
  # required by bower installer
  git \
  language-pack-en \
  build-essential \
  python${PYTHON_VERSION}-dev \
  python${PYTHON_VERSION}-distutils \
  libmysqlclient-dev \
  libssl-dev \
  # TODO: Current version of Pillow (9.5.0) doesn't provide pre-built wheel for python 3.12,
  # So this apt package is needed for building Pillow on 3.12,
  # and can be removed when version of Pillow is upgraded to 10.5.0+
  libjpeg-dev \
  # mysqlclient >= 2.2.0 requires pkg-config.
  pkg-config \
  libcairo2-dev && \
  rm -rf /var/lib/apt/lists/*

# Use UTF-8.
RUN locale-gen en_US.UTF-8
ENV LANG en_US.UTF-8
ENV LANGUAGE en_US:en
ENV LC_ALL en_US.UTF-8

ARG COMMON_APP_DIR="/edx/app"
ARG COMMON_CFG_DIR="/edx/etc"
ARG DISCOVERY_SERVICE_NAME="discovery"
ARG DISCOVERY_APP_DIR="${COMMON_APP_DIR}/${DISCOVERY_SERVICE_NAME}"
ARG DISCOVERY_VENV_DIR="${COMMON_APP_DIR}/${DISCOVERY_SERVICE_NAME}/venvs/${DISCOVERY_SERVICE_NAME}"
ARG DISCOVERY_CODE_DIR="${DISCOVERY_APP_DIR}/${DISCOVERY_SERVICE_NAME}"
ARG DISCOVERY_NODEENV_DIR="${DISCOVERY_APP_DIR}/nodeenvs/${DISCOVERY_SERVICE_NAME}"

ENV PATH "${DISCOVERY_VENV_DIR}/bin:${DISCOVERY_NODEENV_DIR}/bin:$PATH"
ENV DISCOVERY_CFG "/edx/etc/discovery.yml"
ENV DISCOVERY_CODE_DIR "${DISCOVERY_CODE_DIR}"
ENV DISCOVERY_APP_DIR "${DISCOVERY_APP_DIR}"
ENV PYTHON_VERSION "${PYTHON_VERSION}"

RUN curl -sS https://bootstrap.pypa.io/get-pip.py | python${PYTHON_VERSION}
RUN pip install virtualenv

RUN virtualenv -p python${PYTHON_VERSION} --always-copy ${DISCOVERY_VENV_DIR}

# No need to activate discovery venv as it is already in path
RUN pip install nodeenv

RUN nodeenv ${DISCOVERY_NODEENV_DIR} --node=16.14.0 --prebuilt && npm install -g npm@8.5.x

# Working directory will be root of repo.
WORKDIR ${DISCOVERY_CODE_DIR}

# Copy over repository
COPY . .

RUN npm install --production && ./node_modules/.bin/bower install --allow-root --production && ./node_modules/.bin/webpack --config webpack.config.js --progress

# Expose canonical Discovery port
EXPOSE 8381

FROM app as prod

ENV DJANGO_SETTINGS_MODULE "course_discovery.settings.production"

RUN pip install -r ${DISCOVERY_CODE_DIR}/requirements/production.txt

RUN DISCOVERY_CFG=minimal.yml OPENEDX_ATLAS_PULL=true make pull_translations

CMD gunicorn --bind=0.0.0.0:8381 --workers 2 --max-requests=1000 -c course_discovery/docker_gunicorn_configuration.py course_discovery.wsgi:application

FROM app as dev

ENV DJANGO_SETTINGS_MODULE "course_discovery.settings.devstack"

RUN pip install -r ${DISCOVERY_CODE_DIR}/requirements/django.txt
RUN pip install -r ${DISCOVERY_CODE_DIR}/requirements/local.txt

RUN DISCOVERY_CFG=minimal.yml OPENEDX_ATLAS_PULL=true make pull_translations

# Devstack related step for backwards compatibility
RUN touch ${DISCOVERY_APP_DIR}/discovery_env

CMD while true; do python ./manage.py runserver 0.0.0.0:8381; sleep 2; done

###########################################################
# Define k8s target
FROM prod as kubernetes
ENV DISCOVERY_SETTINGS='kubernetes'
ENV DJANGO_SETTINGS_MODULE="course_discovery.settings.$DISCOVERY_SETTINGS"
