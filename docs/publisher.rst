Publisher
=========

The ``publisher`` tool is an information management system that supports the course authoring, review, and approval workflow. The tool manages courses as they transition through the lifecycle of creation (across various subsystems), release/publication to the edX.org marketing site, and eventual retirement/archival.

Note: This app is primarily built for the edX.org use case.


Configure Emails
----------------
The publisher tool supports notifying responsible parties when users comment on courses and course runs. Notifications are sent via Django's email backend. In order to send emails the ``enable_publisher_email_notifications`` switch must be activated, and the following settings must be defined:

+------------------------------------+----------------------------------------------------------------------------+--------------------------------------------------------------------------+
| Setting                            | Description                                                                | Value                                                                    |
+====================================+============================================================================+==========================================================================+
| PUBLISHER_FROM_EMAIL               | Official email address for sending emails.                                 | Email address                                                            |
+------------------------------------+----------------------------------------------------------------------------+--------------------------------------------------------------------------+

Since the publisher tool uses the built-in Django email functionality, any Django email backend can be used. For info on configuring email backends see `django_email`_.

.. _django_email: https://docs.djangoproject.com/en/1.10/topics/email/

We at edX.org use Amazon's Simple Email Service (SES) (`amazon_ses`_). If you'd also like to use SES, the django-ses (`django_ses`_) is installed as a base requirement. Simply define values for the settings below to configure the backend.

.. _amazon_ses: https://aws.amazon.com/ses/
.. _django_ses: https://github.com/django-ses/django-ses

+------------------------------------+----------------------------------------------------------------------------+--------------------------------------------------------------------------+
| Setting                            | Description                                                                | Value                                                                    |
+====================================+============================================================================+==========================================================================+
| EMAIL_BACKEND                      | django_ses.SESBackend                                                      | The backend to use for sending emails.                                   |
+------------------------------------+----------------------------------------------------------------------------+--------------------------------------------------------------------------+
| AWS_ACCESS_KEY_ID                  | YOUR-ACCESS-KEY-ID                                                         | (This should be set to the value from the AWS account.)                  |
+------------------------------------+----------------------------------------------------------------------------+--------------------------------------------------------------------------+
| AWS_SECRET_ACCESS_KEY              | YOUR-SECRET-ACCESS-KEY                                                     | (This should be set to the value from the AWS account.)                  |
+------------------------------------+----------------------------------------------------------------------------+--------------------------------------------------------------------------+
| AWS_SES_REGION_NAME                | Region your SES service is using.                                          | (This should be set to the value from the AWS account.)                  |
+------------------------------------+----------------------------------------------------------------------------+--------------------------------------------------------------------------+
| AWS_SES_REGION_ENDPOINT            | Region your SES service is using.                                          | (This should be set to the value from the AWS account.)                  |
+------------------------------------+----------------------------------------------------------------------------+--------------------------------------------------------------------------+
