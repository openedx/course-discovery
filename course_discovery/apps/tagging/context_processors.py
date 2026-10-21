from django.conf import settings


def tagging(request):
    """
    Add some constants to the context.
    """
    return {
        'HEADER_LOGO_URL': settings.HEADER_LOGO_URL,
    }
