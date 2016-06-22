""" Admin configuration for core models. """

from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from django.utils.translation import ugettext_lazy as _

from course_discovery.apps.core.forms import UserThrottleRateForm
from course_discovery.apps.core.models import User, UserThrottleRate, Currency


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
