Testing
=======

The command below runs the Python tests and code quality validation—Pylint and PEP8.

.. code-block:: bash

    $ make validate

Code quality validation can be run independently with:

.. code-block:: bash

    $ make quality

httpretty
---------

edX uses `httpretty <http://httpretty.readthedocs.org/en/latest/>`_ a lot to mock HTTP endpoints; however,
`a bug in httpretty <https://github.com/gabrielfalcao/HTTPretty/issues/65>`_ (that is closed, but still a problem)
prevents us from using it in this repository. Were you to use `httpretty`, you would find that, although you might
mock an OAuth2 endpoint, `httpretty` blocks requests to Elasticsearch, leading to test failures.

Given our extensive use of Elasticsearch, and need to mock HTTP endpoints, we use the
`responses <https://github.com/getsentry/responses>`_ library. It's API is practically the same as that of `httpretty.
