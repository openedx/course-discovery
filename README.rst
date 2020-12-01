Course Discovery Service  |Codecov|_
==============================================
.. |Codecov| image:: http://codecov.io/github/edx/course-discovery/coverage.svg?branch=master
.. _Codecov: http://codecov.io/github/edx/course-discovery?branch=master

Service providing access to consolidated course and program metadata.

Documentation
-------------

`Documentation <https://edx-discovery.readthedocs.io/en/latest/>`_ is hosted on Read the Docs. The source is hosted in this repo's `docs <https://github.com/edx/course-discovery/tree/master/docs>`_ directory. The docs are automatically rebuilt and redeployed when commits are merged to master. To contribute, please open a PR against this repo.

License
-------

The code in this repository is licensed under version 3 of the AGPL unless otherwise noted. Please see the LICENSE_ file for details.

.. _LICENSE: https://github.com/edx/course-discovery/blob/master/LICENSE

How To Contribute
-----------------

Contributions are welcome. Please read `How To Contribute <https://github.com/edx/edx-platform/blob/master/CONTRIBUTING.rst>`_ for details. Even though it was written with ``edx-platform`` in mind, these guidelines should be followed for Open edX code in general.

Development
-----------

Using elasticsearch locally
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
To use elasticsearch locally, and to update your index after adding new data that you want elasticsearch to access
run:

.. code-block:: shell

    $ ./manage.py update_index --disable-change-limit


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

.. _pytest.ini file: https://github.com/edx/course-discovery/blob/master/pytest.ini
.. _pytest-xdist does not support pdb.set_trace(): https://github.com/pytest-dev/pytest/issues/390#issuecomment-112203885
.. _pytest-no-xdist.ini file: https://github.com/edx/course-discovery/blob/master/pytest=no-xdist.ini

Reporting Security Issues
-------------------------

Please do not report security issues in public. Please email security@edx.org.

Get Help
--------

Ask questions and discuss this project on `Slack <https://openedx.slack.com/messages/general/>`_ or in the `edx-code Google Group <https://groups.google.com/forum/#!forum/edx-code>`_.
