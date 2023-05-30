Course Discovery Service
###################

| |status-badge| |license-badge| |CI| |Codecov|

Service providing access to consolidated course and program metadata.

Getting Started with Development
********************************

This repository works with openedx `devstack`_. Once the devstack has been set up and provisioned, run the
following commands in devstack directory to access Discovery shell and perform operations as needed

.. code-block:: shell

    $ make dev.up.discovery
    $ make discovery-shell
    $ make requirements
    $ make validate


Using elasticsearch locally
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
To use elasticsearch locally, and to update your index after adding new data that you want elasticsearch to access
run:

.. code-block:: shell

    $ ./manage.py update_index --disable-change-limit


To delete elasticsearch old indexes locally you have to use

.. code-block:: shell

    $ ./manage.py remove_unused_indexes

This command will purge the oldest indexes, freeing up disk space. This command will never delete the currently used indexes.


Also you can use base commands by django-elasticsearch-dsl library.

Delete all the currently used indexes in Elasticsearch:

.. code-block:: shell

    $ ./manage.py search_index --delete [-f] [--models [app[.model] app[.model] ...]]

Create the indices and their mapping in Elasticsearch:

.. code-block:: shell

    $ ./manage.py search_index --create [--models [app[.model] app[.model] ...]]

Populate the Elasticsearch mappings with the django models data (index need to be existing):

.. code-block:: shell

    $ ./manage.py search_index --populate [--models [app[.model] app[.model] ...]] [--parallel]

Recreate and repopulate the indices:

.. code-block:: shell

    $ ./manage.py search_index --rebuild [-f] [--models [app[.model] app[.model] ...]] [--parallel]

Please use the link to get more https://django-elasticsearch-dsl.readthedocs.io/en/latest/management.html


**WARNING:** Be aware that `search_index` command works without sanity index check. So be careful to use it.

Working with memcached locally
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Some endpoints, such as /api/v1/courses, have their responses cached in memcached through mechanisms such as the
CompressedCacheResponseMixin. This caching may make it difficult to see code changes reflected in various endpoints
without first clearing the cache or updating the cache keys. You can update the cache keys by going to any
course_metadata model in the admin dashboard and clicking save. To flush your local memcached, make sure the
edx.devstack.memcached container is up and run:

.. code-block:: shell

    $ telnet localhost 11211
    $ flush_all
    $ quit


Running Tests Locally, Fast
~~~~~~~~~~~~~~~~~~~~~~~~~~~

There is a test settings file ``course_discovery.settings.test_local`` that allows you to persist the test
database between runs of the unittests (as long as you don't restart your container).  It stores the SQLite
database file at ``/dev/shm``, which is a filesystem backed by RAM.  Using this test file in conjunction with
pytest's ``--reuse-db`` option can significantly cut down on local testing iteration time.  You can use this
as follows: ``pytest course_discovery/apps/course_metadata/tests/test_utils.py --ds=course_discovery.settings.test_local --reuse-db``

The first run will incur the normal cost of database creation (typically around 30 seconds), but the second run
will completely skip that startup cost, since the ``--reuse-db`` option causes pytest to use the already persisted
database in the ``/dev/shm`` directory.  If you need to change models or create databases between runs, you can tell
pytest to recreate the database with ``-recreate-db``.

Debugging Tests Locally
~~~~~~~~~~~~~~~~~~~~~~~

Pytest in this repository uses the `pytest-xdist <https://github.com/pytest-dev/pytest-xdist>`_ package for distributed testing. This is configured in the `pytest.ini file`_. However, `pytest-xdist does not support pdb.set_trace()`_.
In order to use `pdb <https://docs.python.org/3/library/pdb.html>`_ when debugging Python unit tests, you can use the `pytest-no-xdist.ini file`_ instead. Use the ``-c`` option to the pytest command to specify which ini file to use.

For example,

.. code-block:: shell

   pytest -c pytest-no-xdist.ini --ds=course_discovery.settings.test --durations=25 course_discovery/apps/publisher/tests/test_views.py::CourseRunDetailTests::test_detail_page_with_comments

.. _pytest.ini file: https://github.com/openedx/course-discovery/blob/master/pytest.ini
.. _pytest-xdist does not support pdb.set_trace(): https://github.com/pytest-dev/pytest/issues/390#issuecomment-112203885
.. _pytest-no-xdist.ini file: https://github.com/openedx/course-discovery/blob/master/pytest=no-xdist.ini


Getting Help
*************

`Documentation <https://edx-discovery.readthedocs.io/en/latest/>`_ is hosted on Read the Docs. The source is hosted in this repo's `docs <https://github.com/openedx/course-discovery/tree/master/docs>`_ directory. The docs are automatically rebuilt and redeployed when commits are merged to master. To contribute, please open a PR against this repo.

License
*************

The code in this repository is licensed under version 3 of the AGPL unless otherwise noted. Please see the LICENSE_ file for details.

.. _LICENSE: https://github.com/openedx/course-discovery/blob/master/LICENSE

Contributing
************

Contributions are very welcome.
Please read `How To Contribute <https://openedx.org/r/how-to-contribute>`_ for details.

This project is currently accepting all types of contributions, bug fixes,
security fixes, maintenance work, or new features.  However, please make sure
to have a discussion about your new feature idea with the maintainers prior to
beginning development to maximize the chances of your change being accepted.
You can start a conversation by creating a new issue on this repo summarizing
your idea.

The Open edX Code of Conduct
****************************

All community members are expected to follow the `Open edX Code of Conduct`_.

.. _Open edX Code of Conduct: https://openedx.org/code-of-conduct/

Reporting Security Issues
**************************


Please do not report security issues in public. Please email security@openedx.org.

More Help
*********

If you're having trouble, we have discussion forums at
`discuss.openedx.org <https://discuss.openedx.org>`_ where you can connect with others in the
community.

Our real-time conversations are on Slack. You can request a `Slack
invitation`_, then join our `community Slack workspace`_.

For anything non-trivial, the best path is to `open an issue`__ in this
repository with as many details about the issue you are facing as you
can provide.

__ https://github.com/openedx/course-discovery/issues

For more information about these options, see the `Getting Help`_ page.

.. _Slack invitation: https://openedx.org/slack
.. _community Slack workspace: https://openedx.slack.com/
.. _Getting Help: https://openedx.org/getting-help
.. _devstack: https://github.com/openedx/devstack

.. |CI| image:: https://github.com/openedx/course-discovery/workflows/Python%20CI/badge.svg?branch=master
    :target: https://github.com/openedx/course-discovery/actions?query=workflow%3A%22Python+CI%22
    :alt: Test suite status

.. |Codecov| image:: https://codecov.io/github/openedx/course-discovery/coverage.svg?branch=master
    :target: https://codecov.io/github/openedx/course-discovery?branch=master
    :alt: Code coverage

.. |status-badge| image:: https://img.shields.io/badge/Status-Maintained-brightgreen
    :alt: Maintained

.. |license-badge| image:: https://img.shields.io/github/license/openedx/course-discovery.svg
    :target: https://github.com/openedx/course-discovery/blob/master/LICENSE
    :alt: License
