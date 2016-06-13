""" Core context processors. """
from django.conf import settings


def core(_request):
    """ Site-wide context processor. """
    return {
        'platform_name': settings.PLATFORM_NAME
    }
