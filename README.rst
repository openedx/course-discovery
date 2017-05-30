Course Discovery Service  |Travis|_ |Codecov|_
==============================================
.. |Travis| image:: https://travis-ci.org/edx/course-discovery.svg?branch=master
.. _Travis: https://travis-ci.org/edx/course-discovery

.. |Codecov| image:: http://codecov.io/github/edx/course-discovery/coverage.svg?branch=master
.. _Codecov: http://codecov.io/github/edx/course-discovery?branch=master

The Course Discovery service is a data aggregator with several purposes:

1. Allow external parties to access data about Courses in an OpenEdX installation from a single central location (no matter which the system of record for that data is), in a way that can be secured and will not have operational impact on the running OpenEdX installation.
2. Allow other services inside an OpenEdX installation to consume a consolidated source of course content for presentation to users (for instance, for the purposes of course marketing and discoverability).
3. Provide a facility for naming dynamic groups of courses (catalogs) for use by other services in the system (such as coupon fulfillment and external course discovery filtering).

To aid in these goals, the Course Discovery Service collects data from several systems internal to the Open edX installation. These include Otto (the E-Commerce Service), Studio, and in the edX.org implementation, the Drupal marketing site. The data loading framework is designed to make adding additional systems easy.

Documentation
-------------
.. |ReadtheDocs| image:: https://readthedocs.org/projects/open-edx-course-catalog/badge/?version=latest
.. _ReadtheDocs: https://open-edx-course-catalog.readthedocs.io/en/latest/

`Documentation <https://open-edx-course-catalog.readthedocs.io/en/latest/>`_ is hosted on Read the Docs. The source is hosted in this repo's `docs <https://github.com/edx/course-discovery/tree/master/docs>`_ directory. To contribute, please open a PR against this repo.

License
-------

The code in this repository is licensed under version 3 of the AGPL unless otherwise noted. Please see the LICENSE_ file for details.

.. _LICENSE: https://github.com/edx/course-discovery/blob/master/LICENSE

How To Contribute
-----------------

Contributions are welcome. Please read `How To Contribute <https://github.com/edx/edx-platform/blob/master/CONTRIBUTING.rst>`_ for details. Even though it was written with ``edx-platform`` in mind, these guidelines should be followed for Open edX code in general.

Reporting Security Issues
-------------------------

Please do not report security issues in public. Please email security@edx.org.

Get Help
--------

Ask questions and discuss this project on `Slack <https://openedx.slack.com/messages/general/>`_ or in the `edx-code Google Group <https://groups.google.com/forum/#!forum/edx-code>`_.
