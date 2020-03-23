Advanced Usage
==============

This section contains information about advanced usage and operation of the Discovery service.

Elasticsearch
-------------

Discovery uses Elasticsearch 1.5 to provide search functionality.

Index Aliasing
++++++++++++++

Discovery application code uses an `index alias`_ to refer to the search index indirectly. For example, the timestamped ``course_discovery_20160101113005`` index may be assigned and referred to by the alias ``catalog``. Using an alias prevents index maintenance (e.g., the indexing and index swapping performed by ``update_index``) from affecting service uptime.

.. _index alias: https://www.elastic.co/guide/en/elasticsearch/reference/1.5/indices-aliases.html

Boosting
++++++++

Discovery uses Elasticsearch's `function score`_ query to modify ("boost") the relevance score of documents retrieved by search queries. You can find the service's boosting config at ``course_discovery/apps/edx_haystack_extensions/elasticsearch_boost_config.py``, complete with comments explaining what each part does and how it's been tuned.

.. _function score: https://www.elastic.co/guide/en/elasticsearch/reference/1.5/query-dsl-function-score-query.html

Querying Elasticsearch
++++++++++++++++++++++

In addition to running search queries through the Discovery API, you can make HTTP requests directly to Elasticsearch. This is especially useful if you want to tune how relevance scores are computed. These examples show curl being used from a Discovery shell:

.. code-block:: bash

    $ curl 'edx.devstack.elasticsearch:9200/_cat/indices?v'
    $ curl 'edx.devstack.elasticsearch:9200/catalog/_search?pretty=true' -d '{"explain": true, "query": {YOUR QUERY HERE}}'

The `explain`_ parameter tells Elasticsearch to return a detailed breakdown of how relevance scores were calculated. You can get yourself a query to run by intercepting queries made by the application. Add logging to ``course_discovery/apps/edx_haystack_extensions/backends.py::SimpleQuerySearchBackendMixin::build_search_kwargs`` that prints the final value of ``search_kwargs``, then run a search query through the API.

.. _explain: https://www.elastic.co/guide/en/elasticsearch/reference/1.5/search-request-explain.html

Extensions
----------

edX manages two "extension" apps located at ``course_discovery/apps/edx_catalog_extensions`` and ``course_discovery/apps/edx_haystack_extensions`` as part of Discovery. These apps provide edX-specific customizations. They include data migrations, management commands, and search backends specific to edX. We'd like to move these apps to separate repos at some point in the future to avoid confusion. They live here for now until we can determine what other edX-specific components need to be extracted from the general project.

``edx_catalog_extensions`` is disabled by default. edX developers should add ``course_discovery.apps.edx_catalog_extensions`` to ``INSTALLED_APPS`` in a ``private.py`` settings file.

Catalogs
--------

Catalogs are dynamic groups of courses modeled as access-controlled Elasticsearch queries. You can find the ``Catalog`` model in ``course_discovery/apps/catalogs/models.py``.

Permissions
+++++++++++

A catalog's ``viewers`` property returns the users who are allowed to view the catalog and the courses within it. These per-object permissions are implemented using `django-guardian`_.

.. _django-guardian: https://github.com/django-guardian/django-guardian

Administration
++++++++++++++

You can administer catalogs through the LMS at ``/api-admin/catalogs``. You can also modify catalogs using Discovery's Django admin at ``/admin/catalogs/``. The admin interface provides a preview button you can use to view the list of courses contained in a catalog, as well as the standard ``django-guardian`` admin interface for managing user permissions.

Waffle
------

Discovery uses `django-waffle`_ to control the release of new features. This allows us to gradually increase traffic to new features and divert traffic quickly if problems are discovered. Please refer to Waffle's `documentation`_ for an overview of the models you may encounter throughout the codebase.

.. _django-waffle: https://github.com/jsocol/django-waffle
.. _documentation: https://waffle.readthedocs.io/en/latest/

Internationalization
--------------------

All user-facing strings should be marked for translation. edX runs this application in English, but our open source users may choose to use another language. Marking strings for translation ensures our users have this choice. Refer to edX's `i18n guidelines`_ for more details.

.. _i18n guidelines: https://edx.readthedocs.io/projects/edx-developer-guide/en/latest/internationalization/i18n.html

Updating Translated Strings
+++++++++++++++++++++++++++

Like most edX projects, Discovery uses Transifex to translate content. At edX, the translation process is automated. Every week, changes to source code strings are extracted as translations, which are merged back to the repo and pushed to edX's Transifex resources. Translated strings are also merged back into the repo every week.

Open Source contributors can use ``make extract_translations`` to extract source file string changes, ``make push_translations`` to push changes to Transifex (assuming credentials are available), and ``make pull_translations`` to pull translations from Transifex.

OAuth2
------

The Discovery service uses the OAuth 2.0 protocol for authentication. The LMS currently serves as the OAuth2 provider.

If you're using `devstack`_, OAuth2 should be configured for you. If you need to configure OAuth2 manually, you need to register a new client with the OAuth2 provider (the LMS) and update Discovery's Django settings with the newly created credentials.

.. _devstack: https://github.com/edx/devstack

A new OAuth 2.0 client can be created at ``http://localhost:18000/admin/oauth2_provider/application/``.

    1. Click the :guilabel:`Add Application` button.
    2. Leave the user field blank.
    3. Specify the name of this service, ``credentials``, as the client name.
    4. Set the :guilabel:`URL` to the root path of this service: ``http://localhost:8150/``.
    5. Set the :guilabel:`Redirect URL` to the complete endpoint: ``http://localhost:18150/complete/edx-oauth2/``.
    6. Copy the :guilabel:`Client ID` and :guilabel:`Client Secret` values. They will be used later.
    7. Select :guilabel:`Confidential` as the client type.
    8. Select :guilabel:`Authorization code` as the authorization grant type.
    9. Click :guilabel:`Save`.

You can create a new OAuth 2.0 application on the LMS at ``/admin/oauth2_provider/application/``:

    1. Click the ``Add Application`` button.
    2. Leave the user field blank.
    3. Specify the name of this service, ``discovery``, as the client name.
    4. Set the ``URL`` to the root path of this service: ``http://localhost:18381``.
    5. Set the ``Redirect URL`` to the complete endpoint: ``http://localhost:18381/complete/edx-oauth2/``.
    6. Copy the ``Client ID`` and ``Client Secret`` values. They will be used later.
    7. Select ``Confidential (Web applications)`` as the client type.
    8. Select ``Authorization code`` as the authorization grant type.
    9. Click ``Save``.

Finally, copy the newly created ``Client ID`` and ``Client Secret`` values to Discovery's settings (in ``course_discovery/settings/private.py``, if running locally).

Publisher
---------

"Publisher" is an information management tool meant to support the course authoring, review, and approval workflow. The tool can be used to manage course metadata and is designed for use with the Drupal site that hosts edx.org.
