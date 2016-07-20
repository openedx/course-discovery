""" Core context processors. """
from django.conf import settings
from django.utils.translation import get_language_bidi


def core(_request):
    """ Site-wide context processor. """
    return {
        'platform_name': settings.PLATFORM_NAME,
        'language_bidi': get_language_bidi()
    }
