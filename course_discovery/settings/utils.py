from os import environ

from django.core.exceptions import ImproperlyConfigured


def get_env_setting(setting):
    """ Get the environment setting or raise exception """
    try:
        return environ[setting]
    except KeyError:
        error_msg = "Set the [{}] env variable!".format(setting)
        raise ImproperlyConfigured(error_msg)
