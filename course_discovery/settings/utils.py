from os import environ

from django.core.exceptions import ImproperlyConfigured
from django.http import JsonResponse


def get_env_setting(setting):
    """ Get the environment setting or raise exception """
    try:
        return environ[setting]
    except KeyError:
        error_msg = "Set the [{}] env variable!".format(setting)
        raise ImproperlyConfigured(error_msg)


def stub_user_info_response(request):
    """ Stub the user info endpoint response of the OAuth2 provider. """

    data = {
        'family_name': 'stub',
        'preferred_username': 'staff',
        'given_name': 'user',
        'email': 'staff@example.com',
    }
    return JsonResponse(data)
