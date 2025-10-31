FROM ubuntu:jammy as app

ARG PYTHON_VERSION=3.12

ENV DEBIAN_FRONTEND=noninteractive
ENV TZ=UTC

# System requirements.
RUN apt-get update && \
  apt-get install -y software-properties-common curl git locales && \
  apt-add-repository -y ppa:deadsnakes/ppa && \
  apt-get update && \
  apt-get install -qy \
  gettext \
  build-essential \
  default-libmysqlclient-dev \
  libssl-dev \
  libjpeg-dev \
  pkg-config \
  libcairo2-dev \
  python3-pip \
  python${PYTHON_VERSION} \
  python${PYTHON_VERSION}-dev && \
  rm -rf /var/lib/apt/lists/*

# Use UTF-8.
RUN locale-gen en_US.UTF-8
ENV LANG=en_US.UTF-8
ENV LANGUAGE=en_US:en
ENV LC_ALL=en_US.UTF-8

ARG COMMON_APP_DIR="/edx/app"
ARG COMMON_CFG_DIR="/edx/etc"
ARG DISCOVERY_SERVICE_NAME="discovery"
ARG DISCOVERY_APP_DIR="${COMMON_APP_DIR}/${DISCOVERY_SERVICE_NAME}"
ARG DISCOVERY_VENV_DIR="${COMMON_APP_DIR}/${DISCOVERY_SERVICE_NAME}/venvs/${DISCOVERY_SERVICE_NAME}"
ARG DISCOVERY_CODE_DIR="${DISCOVERY_APP_DIR}/${DISCOVERY_SERVICE_NAME}"
ARG DISCOVERY_NODEENV_DIR="${DISCOVERY_APP_DIR}/nodeenvs/${DISCOVERY_SERVICE_NAME}"

ENV PATH="${DISCOVERY_VENV_DIR}/bin:${DISCOVERY_NODEENV_DIR}/bin:$PATH"
ENV DISCOVERY_CFG="/edx/etc/discovery.yml"
ENV DISCOVERY_CODE_DIR="${DISCOVERY_CODE_DIR}"
ENV DISCOVERY_APP_DIR="${DISCOVERY_APP_DIR}"
ENV PYTHON_VERSION="${PYTHON_VERSION}"

# Setup zoneinfo for Python 3.12
RUN ln -snf /usr/share/zoneinfo/$TZ /etc/localtime && echo $TZ > /etc/timezone

# Install pip and virtualenv
RUN python${PYTHON_VERSION} -m ensurepip --upgrade && \
    pip install --upgrade pip virtualenv nodeenv

RUN virtualenv -p python${PYTHON_VERSION} --always-copy ${DISCOVERY_VENV_DIR}

RUN nodeenv ${DISCOVERY_NODEENV_DIR} --node=16.14.0 --prebuilt && npm install -g npm@8.5.x

# Working directory will be root of repo.
WORKDIR ${DISCOVERY_CODE_DIR}

# Copy over repository
COPY . .

RUN npm install --production && \
    ./node_modules/.bin/bower install --allow-root --production && \
    ./node_modules/.bin/webpack --config webpack.config.js --progress

# Expose canonical Discovery port
EXPOSE 8381

FROM app as prod
ENV DJANGO_SETTINGS_MODULE="course_discovery.settings.production"

RUN pip install -r ${DISCOVERY_CODE_DIR}/requirements/production.txt
RUN DISCOVERY_CFG=minimal.yml OPENEDX_ATLAS_PULL=true make pull_translations

CMD gunicorn --bind=0.0.0.0:8381 --workers 2 --max-requests=1000 \
    -c course_discovery/docker_gunicorn_configuration.py course_discovery.wsgi:application

FROM app as dev
ENV DJANGO_SETTINGS_MODULE="course_discovery.settings.devstack"

RUN pip install -r ${DISCOVERY_CODE_DIR}/requirements/django.txt && \
    pip install -r ${DISCOVERY_CODE_DIR}/requirements/local.txt

RUN DISCOVERY_CFG=minimal.yml OPENEDX_ATLAS_PULL=true make pull_translations

# Devstack related step for backwards compatibility
RUN touch ${DISCOVERY_APP_DIR}/discovery_env

CMD while true; do python ./manage.py runserver 0.0.0.0:8381; sleep 2; done

###########################################################
# Define k8s target
FROM prod as kubernetes
ENV DISCOVERY_SETTINGS='kubernetes'
ENV DJANGO_SETTINGS_MODULE="course_discovery.settings.$DISCOVERY_SETTINGS"