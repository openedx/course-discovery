Getting Started
===============

This guide will walk you through the steps necessary to run the course-discovery service locally, on your host. In the future, we intend to switch to Docker to avoid the need for many of these manual steps.


Install dependencies
--------------------

If you have not already done so, create and activate a virtualenv running Python 3.5. We suggest using `virtualenvwrapper`_.

.. _virtualenvwrapper: https://virtualenvwrapper.readthedocs.org/en/latest/

.. note:: Installing virtualenvwrapper with pip on OS X El Capitan may result
   in a strange OSError due to `a compatibility issue with the six package
   <https://github.com/pypa/pip/issues/3165>`_. In this case, instruct pip to
   ignore six:

   .. code-block:: bash

       $ pip install virtualenvwrapper --upgrade --ignore-installed six

Install dependencies as follows:

.. code-block:: bash

    $ mkvirtualenv --python=$(which python3) discovery
    $ workon discovery
    $ make requirements

Unless otherwise stated, assume all commands below are executed within the virtualenv. 


Install Elasticsearch
---------------------

The course-discovery service uses Elasticsearch (ES) to allow searching for course and program data. Elasticsearch is built using Java, and requires at least Java 8 in order to run. You will need to install the `JDK`_ if you haven't already. To install ES, download and unzip a file of your choice from https://www.elastic.co/downloads/past-releases/elasticsearch-1-5-2. It doesn't matter where you leave it. Locate the ES binary and start the server with:

.. code-block:: bash

    $ bin/elasticsearch

.. _JDK: http://www.oracle.com/technetwork/java/javase/downloads/jdk8-downloads-2133151.html

Navigating ES can be challenging if you don't have much experience with it. The `elasticsearch-head`_ plugin
offers a web-based front end to help with this. To install elasticsearch-head run the following from the root of the elasticsearch-1.5.2 directory:

.. code-block:: bash

    $ bin/plugin -install mobz/elasticsearch-head/1.x

.. _elasticsearch-head: https://mobz.github.io/elasticsearch-head/

You should now be able to access the front end at http://localhost:9200/_plugin/head/.


Run migrations
--------------

By default, local installations use SQLite to create a database named ``default.db``. To apply migrations, run:

.. code-block:: bash

    $ make migrate

If you don't have ES running when you run this, you will see an error after migrations are applied. The error comes from a post-migration hook we use for creating an index and a corresponding alias in ES after migrations are run.


Start the server
----------------

You can now start the server with:

.. code-block:: bash

    $ ./manage.py runserver 8008

Access http://localhost:8008 in your browser and you should see the query preview page. You can run the service at any port of your choosing; these docs will use 8008.

Having a superuser will make it easy for you to sign into the Django admin. Do so as follows:

.. code-block:: bash

    $ ./manage.py createsuperuser

Use the username and password you provided to sign into the Django admin at http://localhost:8008/admin. You should be able to see tables representing all of the application's models.


LMS integration
---------------

To integrate with the LMS, bring up the LMS and navigate to http://localhost:8000/admin/catalog/catalogintegration/. Click "Add catalog integration," and add the URL to the course-discovery service running on your host: ``http://192.168.33.1:8008/api/v1/``.

.. note:: When inside the Vagrant VM, you need to use a special IP to refer to your host. You can find it by running ``ifconfig`` and looking at the IPV4 address for vboxnet0. It's usually 192.168.33.1.

In order for the LMS running in the Vagrant VM to access course-discovery, you will need to run it at 0.0.0.0:8008.

.. code-block:: bash

    $ ./manage.py runserver 0.0.0.0:8008


Private settings
----------------

When developing locally, it may be useful to have settings overrides that you do not wish to commit to the repository.
If you need such overrides, create a file :file:`course_discovery/settings/private.py`. This file's values are
read by :file:`course_discovery/settings/local.py`, but ignored by Git.

If you are an edX employee, see :ref:`edx-extensions`.


Configure partners
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
| courses-api-url               | LMS Courses API Endpoint                | https://lms.example.com/api/courses/v1/            |
+-------------------------------+-----------------------------------------+----------------------------------------------------+
| ecommerce-api-url             | Ecommerce API Endpoint                  | https://ecommerce.example.com/api/v2/              |
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
