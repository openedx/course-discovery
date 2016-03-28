""" Admin configuration for ietf language tag models. """

from django.contrib import admin

from course_discovery.apps.ietf_language_tags.models import Locale


admin.site.register(Locale)
