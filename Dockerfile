FROM ubuntu:jammy as app

ARG PYTHON_VERSION=3.12

ENV DEBIAN_FRONTEND noninteractive
ENV TZ=UTC

# System requirements + Firefox
RUN apt-get update && \
  apt-get install -y software-properties-common && \
  apt-add-repository -y ppa:deadsnakes/ppa && \
  apt-get update && \
  apt-get install -y \
  pkg-config \
  libcairo2-dev \
  python3-pip \
  python3.12 \
  python3.12-dev \
  build-essential \
  default-libmysqlclient-dev \
  libjpeg-dev \
  zlib1g-dev \
  libfreetype6-dev \
  liblcms2-dev \
  libtiff-dev \
  libwebp-dev \
  gettext \
  wget \
  curl \
  grep \
  git \
  unzip \
  locales \
  xvfb \
  libgtk-3-0 \
  libdbus-glib-1-2 \
  libasound2 \
  libx11-xcb1 \
  libxcb-shm0 \
  libxcb1 \
  libxcb-dri3-0 \
  libxcomposite1 \
  libxdamage1 \
  libxrandr2 \
  libxext6 \
  libxfixes3 \
  libnss3 \
  libxrender1 \
  libxtst6 \
  libffi7 \
  libgl1 \
  libpango-1.0-0 \
  libpangocairo-1.0-0 \
  libgdk-pixbuf2.0-0 \
  libatk1.0-0 \
  libcairo2 \
  libatspi2.0-0 && \
  # Install Firefox from Mozilla official binaries (since apt firefox is snap-based on Jammy)
  wget -O /tmp/firefox.tar.gz "https://download.mozilla.org/?product=firefox-latest&os=linux64&lang=en-US" && \
  tar -xvf /tmp/firefox.tar.gz -C /opt/ && \
  ln -s /opt/firefox/firefox /usr/local/bin/firefox && \
  rm /tmp/firefox.tar.gz && \
  rm -rf /var/lib/apt/lists/*

# Install geckodriver
RUN wget -O /tmp/geckodriver.tar.gz "https://github.com/mozilla/geckodriver/releases/download/v0.35.0/geckodriver-v0.35.0-linux64.tar.gz" && \
    tar -xzf /tmp/geckodriver.tar.gz -C /usr/local/bin/ && \
    rm /tmp/geckodriver.tar.gz && \
    chmod +x /usr/local/bin/geckodriver

# Set environment variables for Selenium
ENV GECKODRIVER_PATH=/usr/local/bin/geckodriver

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

# Setup zoneinfo for Python 3.12
RUN ln -snf /usr/share/zoneinfo/$TZ /etc/localtime && echo $TZ > /etc/timezone
# Set python3.12 as the default python3 and install pip
RUN update-alternatives --install /usr/bin/python3 python3 /usr/bin/python${PYTHON_VERSION} 1 && \
    update-alternatives --set python3 /usr/bin/python${PYTHON_VERSION} && \
    curl -sS https://bootstrap.pypa.io/get-pip.py | python3
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
