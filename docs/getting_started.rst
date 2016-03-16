Getting Started
===============

If you have not already done so, create/activate a `virtualenv`_ running Python 3. Unless otherwise stated, assume all terminal code
below is executed within the virtualenv.

.. _virtualenv: https://virtualenvwrapper.readthedocs.org/en/latest/


Install dependencies
--------------------
Dependencies can be installed via the command below.

.. code-block:: bash

    $ make requirements


Local/Private Settings
----------------------
When developing locally, it may be useful to have settings overrides that you do not wish to commit to the repository.
If you need such overrides, create a file :file:`au_amber/settings/private.py`. This file's values are
read by :file:`au_amber/settings/local.py`, but ignored by Git.


Configure edX OpenID Connect (OIDC)
-----------------------------------
This service relies on the edX OIDC (`OpenID Connect`_) authentication provider for login. Note that OIDC is built atop
OAuth 2.0, and this document may use the terms interchangeably. Under our current architecture the LMS serves as our
authentication provider.

Configuring Course Metadata Service to work with OIDC requires registering a new client with the authentication
provider and updating the Django settings for this project with the client credentials.

.. _OpenID Connect: http://openid.net/specs/openid-connect-core-1_0.html


A new OAuth 2.0 client can be created at ``http://127.0.0.1:8000/admin/oauth2/client/``.

    1. Click the :guilabel:`Add client` button.
    2. Leave the user field blank.
    3. Specify the name of this service, ``Course Metadata Service``, as the client name.
    4. Set the :guilabel:`URL` to the root path of this service: ``http://localhost:8003/``.
    5. Set the :guilabel:`Redirect URL` to the OIDC client endpoint: ``https://localhost:8003/complete/edx-oidc/``.
    6. Copy the :guilabel:`Client ID` and :guilabel:`Client Secret` values. They will be used later.
    7. Select :guilabel:`Confidential (Web applications)` as the client type.
    8. Click :guilabel:`Save`.

Now that you have the client credentials, you can update your settings (ideally in
:file:`au_amber/settings/local.py`). The table below describes the relevant settings.

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


Run the server
--------------
The server can be run with `Docker Compose`_. This will start the Course Metadata service, and all of the
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
