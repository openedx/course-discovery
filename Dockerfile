FROM ubuntu:xenial as app

# System requirements.
RUN apt-get update
RUN apt-get install --yes \
	git-core \
	language-pack-en \
	python3.5 \
	python3-pip \
	python3.5-dev \
	build-essential \
	libffi-dev \
	libmysqlclient-dev \
	libxml2-dev \
	libxslt-dev \
	libjpeg-dev \
	libssl-dev
RUN pip3 install nodeenv
RUN pip3 install --upgrade pip setuptools
RUN rm -rf /var/lib/apt/lists/*

# Python is Python3.
RUN ln -s /usr/bin/pip3 /usr/bin/pip
RUN ln -s /usr/bin/python3 /usr/bin/python

# Use UTF-8.
RUN locale-gen en_US.UTF-8
ENV LANG en_US.UTF-8
ENV LANGUAGE en_US:en
ENV LC_ALL en_US.UTF-8

# Make necessary directories and environment variables.
RUN mkdir -p /edx/var/discovery/staticfiles
RUN mkdir -p /edx/var/discovery/media
ENV DJANGO_SETTINGS_MODULE course_discovery.settings.production

# Working directory will be root of repo.
WORKDIR /edx/app/discovery

# Copy just JS requirements and install them.
COPY package.json package.json
COPY package-lock.json package-lock.json
RUN nodeenv /edx/app/nodeenv --node=12.11.1 --prebuilt
ENV PATH /edx/app/nodeenv/bin:${PATH}
RUN npm install --production
COPY bower.json bower.json
RUN ./node_modules/.bin/bower install --allow-root --production

# Copy just Python requirements & install them.
COPY requirements/ requirements/
RUN pip install -r requirements/production.txt

# Copy over rest of code.
# We do this AFTER requirements so that the requirements cache isn't busted
# every time any bit of code is changed.
COPY . .

# Expose canoncal Discovery port
EXPOSE 8381

CMD gunicorn --bind=0.0.0.0:8381 --workers 2 --max-requests=1000 -c course_discovery/docker_gunicorn_configuration.py course_discovery.wsgi:application

FROM app as devstack
ENV DISCOVERY_CFG /edx/app/discovery/devstack.yml
RUN make static

FROM app as newrelic
RUN pip install newrelic
CMD newrelic-admin run-program gunicorn --bind=0.0.0.0:8381 --workers 2 --max-requests=1000 -c course_discovery/docker_gunicorn_configuration.py course_discovery.wsgi:application
