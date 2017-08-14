"""
Debug Toolbar configuration.

These settings may be insecure, and should only be used for local development.
See http://django-debug-toolbar.readthedocs.io/en/stable/configuration.html for additional settings.
"""
DEBUG_TOOLBAR_CONFIG = {
    'SHOW_TOOLBAR_CALLBACK': (lambda __: True),
}
