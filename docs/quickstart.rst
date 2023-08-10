Quickstart
==========

This section covers information you need to know to run and develop for the Discovery service.

Devstack
--------

Discovery is part of edX's Docker-based "devstack." To run the service locally, follow along with the instructions in the https://github.com/edx/devstack repo's `README`_.

.. _README: https://github.com/edx/devstack/blob/master/README.rst

Devstack will allow you to run all edX services together. If you only need Discovery, you can run just the services it requires:

.. code-block:: bash

    $ make dev.up.discovery

Data Loaders
------------

Run the data loaders using the ``refresh_course_metadata`` management command to populate a Discovery instance with data. Open a Discovery shell with ``make discovery-shell``, then run:

.. code-block:: bash

    $ ./manage.py refresh_course_metadata

By default, ``refresh_course_metadata`` loads data for every "partner" in the system. Partners are site tenants, like edx.org. You can view and create tenants using the Django admin at ``/admin/core/partner/``. To load data for a specific tenant:

.. code-block:: bash

    $ ./manage.py refresh_course_metadata --partner_code <SHORT CODE HERE>

Search Indexing
---------------

Once you've loaded data into your Discovery instance, you may want to run Elasticsearch queries against it. Doing so requires indexing the data you've loaded, which you can do by running the ``update_index`` management command. Open a Discovery shell with ``make discovery-shell``, then run:

.. code-block:: bash

    $ ./manage.py update_index --disable-change-limit

Once indexing completes, you can run search queries against the newly created index through the API. For more on this, visit ``/api-docs``.

Tests
-----

Use Docker Compose to run tests just like Travis does. The ``.travis.yml`` file is a good reference if you want to run the entire test suite. You'll notice that a Docker Compose file hosted in this repo is used to run tests instead of the Compose files in the devstack repo. This Compose file defines special test settings and has yet to be consolidated with the Compose files in the devstack repo.

To run specific tests, bring up the services used for testing with ``make travis_up``.  To run the tests in ``course_discovery/apps/api/v1/tests/test_views/test_programs.py``:

.. code-block:: bash

    $ docker-compose -f .travis/docker-compose-travis.yml exec course-discovery bash -c '. /edx/app/discovery/venvs/discovery/bin/activate && cd /edx/app/discovery/discovery && pytest course_discovery/apps/api/v1/tests/test_views/test_programs.py'

When you're done, take down the services you brought up with ``make travis_down``.
