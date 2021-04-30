"""
Helper methods for Edly Sites API.
"""
import logging

from edly_discovery_app.api.v1.constants import CLIENT_SITE_SETUP_FIELDS

logger = logging.getLogger(__name__)


def validate_partner_configurations(request_data):
    """
    Identify missing required fields for client's site partner setup.

    Arguments:
        request_data (dict): Request data passed for site setup

    Returns:
        validation_messages (dict): Missing fields information
    """

    validation_messages = {}

    for field in CLIENT_SITE_SETUP_FIELDS:
        if not request_data.get(field, None):
            field_title = field.replace('_', ' ').title()  # Convert data field 'partner_name' to 'Partner Name'
            validation_messages[field] = '{field_title} is Missing'.format(field_title=field_title)

    return validation_messages
