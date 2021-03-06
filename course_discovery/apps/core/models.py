""" Core models. """
from django.conf import settings
from django.contrib.auth.models import AbstractUser
from django.contrib.sites.models import Site
from django.db import models
from django.utils.functional import cached_property
from django.utils.translation import ugettext_lazy as _
from django_extensions.db.models import TimeStampedModel
from edx_rest_api_client.client import OAuthAPIClient
from guardian.mixins import GuardianUserMixin
from simple_history.models import HistoricalRecords


class User(GuardianUserMixin, AbstractUser):
    """Custom user model for use with OpenID Connect."""
    full_name = models.CharField(_('Full Name'), max_length=255, blank=True, null=True)
    referral_tracking_id = models.CharField(_('Referral Tracking ID'), max_length=255, default='affiliate_partner')

    class Meta:
        get_latest_by = 'date_joined'

    def get_full_name(self):
        return self.full_name or super().get_full_name()


class UserThrottleRate(models.Model):
    """Model for configuring a rate limit per-user."""

    user = models.ForeignKey(User, models.CASCADE)
    rate = models.CharField(
        max_length=50,
        help_text=_(
            'The rate of requests to limit this user to. The format is specified by Django'
            ' Rest Framework (see http://www.django-rest-framework.org/api-guide/throttling/).')
    )


class Currency(models.Model):
    """ Table of currencies as defined by ISO-4217. """
    code = models.CharField(max_length=6, primary_key=True, unique=True)
    name = models.CharField(max_length=255)

    def __str__(self):
        return f'{self.code} - {self.name}'

    class Meta:
        verbose_name_plural = 'Currencies'


class Partner(TimeStampedModel):
    name = models.CharField(max_length=128, unique=True, null=False, blank=False)
    short_code = models.CharField(
        max_length=8, unique=True, null=False, blank=False, verbose_name=_('Short Code'),
        help_text=_('Convenient code/slug used to identify this Partner (e.g. for management commands.)'))
    courses_api_url = models.URLField(max_length=255, null=True, blank=True, verbose_name=_('Courses API URL'))
    lms_coursemode_api_url = models.URLField(
        max_length=255, null=True, blank=True,
        verbose_name=_('Course Mode API URL'))
    ecommerce_api_url = models.URLField(max_length=255, null=True, blank=True, verbose_name=_('E-Commerce API URL'))
    organizations_api_url = models.URLField(max_length=255, null=True, blank=True,
                                            verbose_name=_('Organizations API URL'))
    programs_api_url = models.URLField(max_length=255, null=True, blank=True, verbose_name=_('Programs API URL'))
    marketing_site_api_url = models.URLField(max_length=255, null=True, blank=True,
                                             verbose_name=_('Marketing Site API URL'))
    marketing_site_url_root = models.URLField(max_length=255, null=True, blank=True,
                                              verbose_name=_('Marketing Site URL'))
    marketing_site_api_username = models.CharField(max_length=255, null=True, blank=True,
                                                   verbose_name=_('Marketing Site API Username'))
    marketing_site_api_password = models.CharField(max_length=255, null=True, blank=True,
                                                   verbose_name=_('Marketing Site API Password'))

    studio_url = models.URLField(max_length=255, null=True, blank=True, verbose_name=_('Studio URL'))
    publisher_url = models.URLField(
        max_length=255, null=True, blank=True, verbose_name=_('Publisher URL'),
        help_text=_('The base URL of your publisher service, if used. Example: https://publisher.example.com/')
    )
    site = models.OneToOneField(Site, models.PROTECT)
    lms_url = models.URLField(max_length=255, null=True, blank=True, verbose_name=_('LMS URL'))
    lms_admin_url = models.URLField(
        max_length=255, null=True, blank=True, verbose_name=_('LMS Admin URL'),
        help_text=_('The public URL of your LMS Django admin. Example: https://lms-internal.example.com/admin'),
    )
    analytics_url = models.URLField(max_length=255, blank=True, verbose_name=_('Analytics API URL'), default='')
    analytics_token = models.CharField(max_length=255, blank=True, verbose_name=_('Analytics Access Token'), default='')

    history = HistoricalRecords()

    def __str__(self):
        return self.name

    class Meta:
        verbose_name = _('Partner')
        verbose_name_plural = _('Partners')

    @property
    def has_marketing_site(self):
        return bool(self.marketing_site_url_root)

    @property
    def uses_publisher(self):
        return settings.ENABLE_PUBLISHER and self.publisher_url

    @cached_property
    def oauth_api_client(self):
        # Does not need to be on the Partner model, but is here for historical reasons and this client is usually used
        # along with URLs from this model. So might as well have it here for convenience.
        return OAuthAPIClient(
            settings.BACKEND_SERVICE_EDX_OAUTH2_PROVIDER_URL,
            settings.BACKEND_SERVICE_EDX_OAUTH2_KEY,
            settings.BACKEND_SERVICE_EDX_OAUTH2_SECRET,
            timeout=settings.OAUTH_API_TIMEOUT,
        )


class SalesforceConfiguration(models.Model):
    partner = models.OneToOneField(Partner, models.CASCADE, related_name='salesforce')
    username = models.CharField(
        max_length=255,
        verbose_name=_('Salesforce Username'),
    )
    password = models.CharField(
        max_length=255,
        verbose_name=_('Salesforce Password'),
    )
    organization_id = models.CharField(
        max_length=255,
        blank=True,
        verbose_name=_('Salesforce Organization Id'),
        default=''
    )
    security_token = models.CharField(
        max_length=255,
        blank=True,
        verbose_name=_('Salesforce Security Token'),
        default=''
    )
    is_sandbox = models.BooleanField(
        verbose_name=_('Is a Salesforce Sandbox?'),
        default=True
    )
    case_record_type_id = models.CharField(
        max_length=255,
        blank=True,
        verbose_name=_('Case Record Type Id'),
        null=True,
    )

    history = HistoricalRecords()
