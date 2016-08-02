""" Admin configuration for core models. """

from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from django.utils.translation import ugettext_lazy as _

from course_discovery.apps.core.forms import UserThrottleRateForm
from course_discovery.apps.core.models import User, UserThrottleRate, Currency, Partner


@admin.register(User)
class CustomUserAdmin(UserAdmin):
    """ Admin configuration for the custom User model. """
    list_display = ('username', 'email', 'full_name', 'first_name', 'last_name', 'is_staff', 'referral_tracking_id')
    fieldsets = (
        (None, {'fields': ('username', 'password', 'referral_tracking_id')}),
        (_('Personal info'), {'fields': ('full_name', 'first_name', 'last_name', 'email')}),
        (_('Permissions'), {'fields': ('is_active', 'is_staff', 'is_superuser', 'groups', 'user_permissions')}),
        (_('Important dates'), {'fields': ('last_login', 'date_joined')}),
    )


@admin.register(UserThrottleRate)
class UserThrottleRateAdmin(admin.ModelAdmin):
    """ Admin configuration for the UserThrottleRate model. """
    form = UserThrottleRateForm
    list_display = ('user', 'rate',)
    raw_id_fields = ('user',)
    search_fields = ('user__username',)


@admin.register(Currency)
class CurrencyAdmin(admin.ModelAdmin):
    list_display = ('code', 'name',)
    ordering = ('code', 'name',)
    search_fields = ('code', 'name',)


@admin.register(Partner)
class PartnerAdmin(admin.ModelAdmin):
    fieldsets = (
        (None, {
            'fields': ('name', 'short_code',)
        }),
        (_('OpenID Connect'), {
            'description': _(
                'OpenID Connect is used for front-end authentication as well as getting access to the APIs.'),
            'fields': ('oidc_url_root', 'oidc_key', 'oidc_secret',)
        }),
        (_('API Configuration'), {
            'description': _('Configure the APIs that will be used to retrieve data.'),
            'fields': ('courses_api_url', 'ecommerce_api_url', 'organizations_api_url', 'programs_api_url',)
        }),
        (_('Marketing Site Configuration'), {
            'description': _('Configure the marketing site URLs that will be used to retrieve data and create URLs.'),
            'fields': ('marketing_site_url_root', 'marketing_site_api_url', 'marketing_site_api_username',
                       'marketing_site_api_password',)
        }),
    )
    list_display = ('name', 'short_code',)
    ordering = ('name', 'short_code',)
    search_fields = ('name', 'short_code',)
