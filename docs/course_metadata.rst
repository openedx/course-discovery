Course Metadata
===============

The ``course_metadata`` app at :file:`course_discovery/apps/course_metadata` primarily deals with getting data from
various external systems and pulling it into the course catalog.

Data Loaders
------------

:file:`course_discovery/apps/course_metadata/data_loaders.py` contains code for retrieving data from different
sources. The ``AbstractDataLoader`` class defines the basic interface, and is currently subclassed by the three
concrete implementations shown below. In the future we may add more data loaders as the requirements of the course
catalog change.

.. automodule:: course_discovery.apps.course_metadata.data_loaders
   :members:

Retrieving Course Metadata
--------------------------

The ``refresh_course_metadata`` command in :file:`course_discovery/apps/course_metadata/management/commands/refresh_course_metadata.py` is used to retrieve metadata. This is run daily in production through a Jenkins job, and can be manually run to set up your local environment. The data loaders are each run in series by the command. The data
loaders should be idempotent -- that is, running this command once will populate the database, and if nothing has
changed upstream then running it again should not change the database.

QuerySets
---------

We use a custom ``QuerySet`` for retrieving active courses, based on the definition of "active" that the LMS uses.

.. autoclass:: course_discovery.apps.course_metadata.query.CourseQuerySet
   :members:

Views
-----

The ``QueryPreviewView`` provides a simple interface to test a query before saving it to a catalog.

.. autoclass:: course_discovery.apps.course_metadata.views.QueryPreviewView
   :members:

Models
------

The ``course_metadata`` contains most of the models used in the course catalog API.

.. automodule:: course_discovery.apps.course_metadata.models
   :members:
   :undoc-members:

Searching for Courses
---------------------

The fields of ``CourseIndex`` and ``CourseRunIndex`` are the fields that can be used in ES queries.

.. automodule:: course_discovery.apps.course_metadata.search_indexes
   :members:
   :undoc-members:
