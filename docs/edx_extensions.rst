.. _edx-extensions:

edX Extensions
==============
edX.org has its own app, ``edx_catalog_extensions``, to contain edX-specific customizations. These include data
migrations, management commands, etc. specific to edX. Non-edX users should NOT use this app. This app
is explicitly disabled by default in all non-test environments.

At some point in the future this app will be moved to a separate repository to avoid confusion. It exists here now
until we can determine what other edX-specific components need to be extracted from the general project.

edX developers should add ``'course_discovery.apps.edx_catalog_extensions'`` to the ``INSTALLED_APPS`` setting in a
``private.py`` settings file.

Settings
========

``HAYSTACK_INDEX_RETENTION_LIMIT``
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Default: ``3``

This field sets an upper bound for the number of indexes that will be retained after
a purge triggered by the 'remove_unused_indexes' command.  This command will never delete the currently used index.