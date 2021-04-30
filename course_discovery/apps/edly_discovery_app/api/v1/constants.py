"""
Constants for Edly Sites API.
"""
from django.utils.translation import ugettext as _

ERROR_MESSAGES = {
    'CLIENT_SITES_SETUP_SUCCESS': _('Client sites setup successful.'),
    'CLIENT_SITES_SETUP_FAILURE': _('Client sites setup failed.'),
}

CLIENT_SITE_SETUP_FIELDS = [
    'lms_site',
    'cms_site',
    'discovery_site',
    'payments_site',
    'wordpress_site',
    'partner_name',
    'partner_short_code',
]
