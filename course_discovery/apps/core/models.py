""" Core models. """

from django.contrib.auth.models import AbstractUser
from django.db import models
from django.utils.translation import ugettext_lazy as _
from django_extensions.db.models import TimeStampedModel


class User(AbstractUser):
    """Custom user model for use with OpenID Connect."""
    full_name = models.CharField(_('Full Name'), max_length=255, blank=True, null=True)

    @property
    def access_token(self):
        """ Returns an OAuth2 access token for this user, if one exists; otherwise None.

        Assumes user has authenticated at least once with edX Open ID Connect.
        """
        try:
            return self.social_auth.first().extra_data[u'access_token']  # pylint: disable=no-member
        except Exception:  # pylint: disable=broad-except
            return None

    class Meta(object):  # pylint:disable=missing-docstring
        get_latest_by = 'date_joined'

    def get_full_name(self):
        return self.full_name or super(User, self).get_full_name()


class UserThrottleRate(models.Model):
    """Model for configuring a rate limit per-user."""

    user = models.ForeignKey(User)
    rate = models.CharField(
        max_length=50,
        help_text=_(
            'The rate of requests to limit this user to. The format is specified by Django'
            ' Rest Framework (see http://www.django-rest-framework.org/api-guide/throttling/).')
    )


class Language(TimeStampedModel):
    """
    Language model.
    """
    iso_code = models.CharField(max_length=2)
    name = models.CharField(max_length=255)

    def __str__(self):
        return self.iso_code


class Locale(TimeStampedModel):
    """
    Locale model.
    """
    iso_code = models.CharField(max_length=5)
    name = models.CharField(max_length=255)
    language = models.ForeignKey(Language)

    def __str__(self):
        return self.iso_code


class Currency(TimeStampedModel):
    """
    Language model.
    """
    iso_code = models.CharField(max_length=2)
    name = models.CharField(max_length=255)

    def __str__(self):
        return self.iso_code
