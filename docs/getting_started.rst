Getting Started
===============

If you have not already done so, create/activate a `virtualenv`_ running Python 3.5. Unless otherwise stated, assume all terminal code
below is executed within the virtualenv.

.. _virtualenv: https://virtualenvwrapper.readthedocs.org/en/latest/

.. note:: Installing virtualenvwrapper with pip on OS X El Capitan may result
   in a strange OSError due to `a compatibility issue with the six package
   <https://github.com/pypa/pip/issues/3165>`_. In this case, instruct pip to
   ignore six:

   .. code-block:: bash

       $ pip install virtualenvwrapper --upgrade --ignore-installed six

Install dependencies
--------------------
Dependencies can be installed via the command below.

.. code-block:: bash

    $ make requirements


Local/Private Settings
----------------------
When developing locally, it may be useful to have settings overrides that you do not wish to commit to the repository.
If you need such overrides, create a file :file:`course_discovery/settings/private.py`. This file's values are
read by :file:`course_discovery/settings/local.py`, but ignored by Git.

If you are an edX employee/developer, see :ref:`edx-extensions`.


Configure edX OpenID Connect (OIDC)
-----------------------------------
This service relies on the edX OIDC (`OpenID Connect`_) authentication provider for login. Note that OIDC is built atop
OAuth 2.0, and this document may use the terms interchangeably. Under our current architecture the LMS serves as our
authentication provider.

Configuring Course Discovery Service to work with OIDC requires registering a new client with the authentication
provider and updating the Django settings for this project with the client credentials.

.. _OpenID Connect: http://openid.net/specs/openid-connect-core-1_0.html


A new OAuth 2.0 client can be created at ``http://127.0.0.1:8000/admin/oauth2/client/``.

    1. Click the :guilabel:`Add client` button.
    2. Leave the user field blank.
    3. Specify the name of this service, ``Course Discovery Service``, as the client name.
    4. Set the :guilabel:`URL` to the root path of this service: ``http://localhost:18381/``.
    5. Set the :guilabel:`Redirect URL` to the OIDC client endpoint: ``http://localhost:18381/complete/edx-oidc/``.
    6. Copy the :guilabel:`Client ID` and :guilabel:`Client Secret` values. They will be used later.
    7. Select :guilabel:`Confidential (Web applications)` as the client type.
    8. Click :guilabel:`Save`.

Now that you have the client credentials, you can update your settings (ideally in
:file:`course_discovery/settings/private.py`). The table below describes the relevant settings.

+-----------------------------------------------------+----------------------------------------------------------------------------+--------------------------------------------------------------------------+
| Setting                                             | Description                                                                | Value                                                                    |
+=====================================================+============================================================================+==========================================================================+
| SOCIAL_AUTH_EDX_OIDC_KEY                            | OAuth 2.0 client key                                                       | (This should be set to the value generated when the client was created.) |
+-----------------------------------------------------+----------------------------------------------------------------------------+--------------------------------------------------------------------------+
| SOCIAL_AUTH_EDX_OIDC_SECRET                         | OAuth 2.0 client secret                                                    | (This should be set to the value generated when the client was created.) |
+-----------------------------------------------------+----------------------------------------------------------------------------+--------------------------------------------------------------------------+
| SOCIAL_AUTH_EDX_OIDC_URL_ROOT                       | OAuth 2.0 authentication URL                                               | http://127.0.0.1:8000/oauth2                                             |
+-----------------------------------------------------+----------------------------------------------------------------------------+--------------------------------------------------------------------------+
| SOCIAL_AUTH_EDX_OIDC_ID_TOKEN_DECRYPTION_KEY        | OIDC ID token decryption key. This value is used to validate the ID token. | (This should be the same value as SOCIAL_AUTH_EDX_OIDC_SECRET.)          |
+-----------------------------------------------------+----------------------------------------------------------------------------+--------------------------------------------------------------------------+


Run migrations
--------------
Local installations use SQLite by default. If you choose to use another database backend, make sure you have updated
your settings and created the database (if necessary). Migrations can be run with `Django's migrate command`_.

.. code-block:: bash

    $ make migrate

.. _Django's migrate command: https://docs.djangoproject.com/en/1.8/ref/django-admin/#django-admin-migrate


Configure Partners
------------------
The Catalog Service is designed to support multiple collections of API endpoints to construct its search
indexes. These collections are represented in the system's domain model as "Partner" entities.  In addition to indexing,
Partners link related top-level system entities -- Courses, Organizations, and Programs -- in order to create logical
index partitions for use during search operations.

To configure a Partner, add a new entry to the system via the Catalog Service administration console found at
``https://catalog.example.com/admin``.  Alternatively you may execute the ``create_or_update_partner`` management
command via the terminal. This command, found in
:file:`course_discovery/apps/core/management/commands/create_or_update_partner.py`, allows service operators to specify
any/all Partner attributes as command arguments for both new and existing Partners, including marketing site
and OIDC authentication credentials.

Required arguments include the ``code`` and ``name`` fields, as follows:

.. code-block:: bash

    $ ./manage.py create_or_update_partner --code='abc' --name='ABC Partner'

Additional optional attributes can be specified:

+-------------------------------+-----------------------------------------+----------------------------------------------------+
| Attribute/Argument            | Description                             | Notes / Example Values                             |
+===============================+=========================================+====================================================+
| courses-api-url               | LMS Courses API Endpoint                | https://lms.example.com/api/v1/courses/            |
+-------------------------------+-----------------------------------------+----------------------------------------------------+
| ecommerce-api-url             | Ecommerce Courses API Endpoint          | https://ecommerce.example.com/api/v1/courses/      |
+-------------------------------+-----------------------------------------+----------------------------------------------------+
| organizations-api-url         | Organizations API Endpoint              | https://orgs.example.com/api/v1/organizations/     |
+-------------------------------+-----------------------------------------+----------------------------------------------------+
| programs-api-url              | Programs API Endpoint                   | https://programs.example.com/api/v1/programs/      |
+-------------------------------+-----------------------------------------+----------------------------------------------------+
| marketing-site-url-root       | Drupal-based Marketing Site URL         | https://www.example.com/                           |
+-------------------------------+-----------------------------------------+----------------------------------------------------+
| marketing-site-api-url        | Drupal Courses API Endpoint             | https://www.example.com/api/v1/courses/            |
+-------------------------------+-----------------------------------------+----------------------------------------------------+
| marketing-site-api-username   | Drupal Courses API Account Username     | (This value comes from the Drupal user account)    |
+-------------------------------+-----------------------------------------+----------------------------------------------------+
| marketing-site-api-password   | Drupal Courses API Account Password     | (This value comes from the Drupal user account)    |
+-------------------------------+-----------------------------------------+----------------------------------------------------+
| oidc-url-root                 | Open edX OpenID Connect URL             | https://lms.example.com/oauth2                     |
+-------------------------------+-----------------------------------------+----------------------------------------------------+
| oidc-key                      | Open edX OpenID Connect Client Key/ID   | (This value comes from the LMS Client record)      |
+-------------------------------+-----------------------------------------+----------------------------------------------------+
| oidc-secret                   | Open edX OpenID Connect Client Secret   | (This value comes from the LMS Client record)      |
+-------------------------------+-----------------------------------------+----------------------------------------------------+


Run the server
--------------
The server can be run with `Docker Compose`_. This will start the Course Discovery service, and all of the
services that it depends on.

.. code-block:: bash

    $ make start-devstack

.. _Docker Compose: https://docs.docker.com/compose/


Install elasticsearch-head
--------------------------
Navigating Elasticsearch can be challenging if you don't have much experience with it. The `elasticsearch-head`_ plugin
offers a web-based front end to help with this. The plugin can be installed in the `es` container with the command below.

.. code-block:: bash

    $ docker exec es /usr/share/elasticsearch/bin/plugin -install mobz/elasticsearch-head

.. _elasticsearch-head: https://mobz.github.io/elasticsearch-head/
