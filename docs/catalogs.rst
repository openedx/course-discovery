Catalogs
========

A catalog is modeled as an Elasticsearch query (see :doc:`elasticsearch`) returning a
list of courses. The ``Catalog`` model lives in :file:`course_discovery/apps/catalogs/models.py`.

.. autoclass:: course_discovery.apps.catalogs.models.Catalog
   :members:

Permissions
-----------

The ``viewers`` property of a catalog gives the users who are allowed to view the catalog and the courses it
contains. We use `django-guardian`_ for per-object permissions.

.. _django-guardian: https://django-guardian.readthedocs.io/en/stable/

Administration
--------------

Catalog administration is primarily done through the LMS at ``/api-admin/catalogs``. However, if you need to modify
a catalog or its query directly, you can do so using the course catalog Django admin at ``/admin/catalogs/``. The
admin interface provides a preview button to directly view the list of courses contained in a catalog, as well as
``django-guardian``'s standard admin for user permissions.
