Configure edX OpenID Connect (OIDC)
===================================

This service relies on the edX OIDC (`OpenID Connect`_) authentication provider for login. Note that OIDC is built atop
OAuth 2.0, and this document may use the terms interchangeably. Under our current architecture the LMS serves as our
authentication provider.

Configuring Course Discovery Service to work with OIDC requires registering a new client with the authentication
provider and updating the Django settings for this project with the client credentials.

.. _OpenID Connect: http://openid.net/specs/openid-connect-core-1_0.html

A new OAuth 2.0 client can be created on the LMS at ``http://127.0.0.1:8000/admin/oauth2/client/``.

    1. Click the :guilabel:`Add client` button.
    2. Leave the user field blank.
    3. Specify the name of this service, ``Course Discovery Service``, as the client name.
    4. Set the :guilabel:`URL` to the root path of this service: ``http://localhost:18381/``.
    5. Set the :guilabel:`Redirect URL` to the OIDC client endpoint: ``http://localhost:18381/complete/edx-oidc/``.
    6. Copy the :guilabel:`Client ID` and :guilabel:`Client Secret` values. They will be used later.
    7. Select :guilabel:`Confidential (Web applications)` as the client type.
    8. Click :guilabel:`Save`.

Now that you have the client credentials, you can update your settings (in
:file:`course_discovery/settings/private.py`, if running locally). The table below describes the relevant settings.

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
