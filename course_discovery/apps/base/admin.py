""" Admin configuration for base models. """

from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from django.utils.translation import ugettext_lazy as _

from course_discovery.apps.base.forms import UserThrottleRateForm
from course_discovery.apps.base.models import User, UserThrottleRate


class CustomUserAdmin(UserAdmin):
    """ Admin configuration for the custom User model. """
    list_display = ('username', 'email', 'full_name', 'first_name', 'last_name', 'is_staff')
    fieldsets = (
        (None, {'fields': ('username', 'password')}),
        (_('Personal info'), {'fields': ('full_name', 'first_name', 'last_name', 'email')}),
        (_('Permissions'), {'fields': ('is_active', 'is_staff', 'is_superuser',
                                       'groups', 'user_permissions')}),
        (_('Important dates'), {'fields': ('last_login', 'date_joined')}),
    )


class UserThrottleRateAdmin(admin.ModelAdmin):
    """ Admin configuration for the UserThrottleRate model. """
    form = UserThrottleRateForm
    raw_id_fields = ('user',)


admin.site.register(User, CustomUserAdmin)
admin.site.register(UserThrottleRate, UserThrottleRateAdmin)
