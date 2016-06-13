Elasticsearch
=============

This service uses Elasticsearch to power the course catalog functionality. This allows users to search courses by
various criteria related to data collected from the E-Commerce Service (Otto) and other potential data sources.

The service is configured to use the `course_catalog` index by default. If you'd like to change the index, or the
URL of the Elasticsearch service, update the `ELASTICSEARCH` setting.

Elasticsearch has a feature called `aliases     <https://www.elastic.co/guide/en/elasticsearch/reference/current/indices-aliases.html>`_.
This feature allows indices to be referenced by an alias. For example, the timestamped course_catalog_20160101113005
index could be assigned the alias course_catalog. It is common practice to reference aliases in code, rather than
indices, to allow for index swapping, reindex, and other maintenance without affecting service uptime. We recommend
following this practice.

Creating an index and alias
---------------------------

The `install_es_indexes` management command should be used when initializing a new alias and index. This command will
check to see if the alias exists, and is linked to an open index. If that check is true, the command will exit
successfully. If that check fails, a new index with a timestamped name (e.g. course_catalog_20160101113005) will be
created; and, the alias will be assigned to the new index.

.. code-block:: bash

    $ ./manage.py install_es_indexes

Query String Syntax
-------------------

We use the query string syntax to search for courses. See `the Elasticsearch documentation`_ for a guide to the
query string syntax, and :doc:`course_metadata` for a list of fields which can be searched.

.. _the Elasticsearch documentation: https://www.elastic.co/guide/en/elasticsearch/reference/current/query-dsl-query-string-query.html#query-string-syntax
