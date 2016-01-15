Elasticsearch
=============

This service uses Elasticsearch to power the course catalog functionality. This allows users to search courses by
various criteria related to data collected from the E-Commerce Service (Otto) and other potential data sources.

The service is configured to use the `course_discovery` index by default. If you'd like to change the index, or the
URL of the Elasticsearch service, update the `ELASTICSEARCH` setting.

Elasticsearch has a feature called `aliases`<https://www.elastic.co/guide/en/elasticsearch/reference/current/indices-aliases.html>.
This feature allows indices to be referenced by an alias. For example, the timestamped course_discovery_20160101113005
index could be assigned the alias course_discovery. It is common practice to reference aliases in code, rather than
indices, to allow for index swapping, reindex, and other maintenance without affecting service uptime. We recommend
following this practice.

Creating an index and alias
---------------------------

The `install_es_indexes` management command should be used when initializing a new alias and index. This command will
check to see if the alias exists, and is linked to an open index. If that check is true, the command will exit
successfully. If that check fails, a new index with a timestamped name (e.g. course_discovery_20160101113005) will be
created; and, the alias will be assigned to the new index.

.. code-block:: bash

    $ ./manage.py install_es_indexes
