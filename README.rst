Part of `edX code`__.

__ http://code.edx.org/

Course Discovery Service  |Travis|_ |Codecov|_
==============================================
.. |Travis| image:: https://travis-ci.org/edx/course-discovery.svg?branch=master
.. _Travis: https://travis-ci.org/edx/course-discovery

.. |Codecov| image:: http://codecov.io/github/edx/course-discovery/coverage.svg?branch=master
.. _Codecov: http://codecov.io/github/edx/course-discovery?branch=master

The Course Discovery API an data aggregator with several purposes:

1. Allow external parties to access data about Courses in an OpenEdX installation
   from a single central location (no matter which the system of record for that
   data is), in a way that can be secured and will not have operational impact
   on the running OpenEdX installation.
2. Allow other services inside an OpenEdX installation to consume a consolidated
   source of course content for presentation to users (for instance, for
   the purposes of course marketing and discoverability).
3. Provide a facility for naming dynamic groups of courses (catalogs) for
   use by other services in the system (such as coupon fulfillment and external
   course discovery filtering).

To aid in these goals, the Course Discovery Service will collect data from
several systems internal to the OpenEdX installation. Initially, this will
just be Otto (the Ecommerce service), and in the future will it will also include
Studio, and in the edX.org implementation, our Drupal marketing site. The design
intention is that additional systems should be cheap to add to the same framework.

Overview
--------

As a standard django application :module:`course_discovery.views` is a useful
entry point, as it defines the APIs that this service will support.

Documentation
-------------

The docs for Course Discovery Service will be on Read the Docs:  https://open-edx-course-discovery.readthedocs.org.

License
-------

The code in this repository is licensed under AGPL unless
otherwise noted.

Please see ``LICENSE.txt`` for details.

How To Contribute
-----------------

Contributions are very welcome.

Please read `How To Contribute <https://github.com/edx/edx-platform/blob/master/CONTRIBUTING.rst>`_ for details.

Even though they were written with ``edx-platform`` in mind, the guidelines
should be followed for Open edX code in general.

Reporting Security Issues
-------------------------

Please do not report security issues in public. Please email security@edx.org.

Mailing List and IRC Channel
----------------------------

You can discuss this code in the `edx-code Google Group`__ or in the ``#edx-code`` IRC channel on Freenode.

__ https://groups.google.com/forum/#!forum/edx-code
