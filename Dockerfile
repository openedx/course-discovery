FROM ubuntu:xenial as app

RUN apt update && \
  apt install -y git-core language-pack-en python3.5 python3-pip python3.5-dev \
  build-essential libffi-dev libmysqlclient-dev libxml2-dev libxslt-dev libjpeg-dev libssl-dev && \
  pip3 install nodeenv && \
  pip3 install --upgrade pip setuptools && \
  rm -rf /var/lib/apt/lists/*

RUN ln -s /usr/bin/pip3 /usr/bin/pip
RUN ln -s /usr/bin/python3 /usr/bin/python

RUN locale-gen en_US.UTF-8
ENV LANG en_US.UTF-8
ENV LANGUAGE en_US:en
ENV LC_ALL en_US.UTF-8

COPY . /edx/app/discovery
WORKDIR /edx/app/discovery

ENV DISCOVERY_CFG /edx/etc/discovery.yml

RUN nodeenv /edx/app/nodeenv --node=8.9.3 --prebuilt
ENV PATH /edx/app/nodeenv/bin:${PATH}

RUN pip install -r requirements.txt
RUN npm install --production
RUN ./node_modules/.bin/bower install --allow-root --production

EXPOSE 8381
CMD gunicorn --bind=0.0.0.0:8381 --workers 2 --max-requests=1000 -c /edx/app/discovery/course_discovery/docker_gunicorn_configuration.py course_discovery.wsgi:application

FROM app as newrelic
RUN pip install newrelic
CMD newrelic-admin run-program gunicorn --bind=0.0.0.0:8381 --workers 2 --max-requests=1000 -c /edx/app/discovery/course_discovery/docker_gunicorn_configuration.py course_discovery.wsgi:application
