"""
URLs for the admin autocomplete lookups.
"""
from django.conf.urls import url

from course_discovery.apps.course_metadata.lookups import (
    CourseAutocomplete, CourseRunAutocomplete, OrganizationAutocomplete, PersonAutocomplete
)
from course_discovery.apps.course_metadata.views import CourseRunSelectionAdmin

urlpatterns = [
    url(r'^update_course_runs/(?P<pk>\d+)/$', CourseRunSelectionAdmin.as_view(), name='update_course_runs',),
    url(r'^course-autocomplete/$', CourseAutocomplete.as_view(), name='course-autocomplete',),
    url(r'^course-run-autocomplete/$', CourseRunAutocomplete.as_view(), name='course-run-autocomplete',),
    url(r'^organisation-autocomplete/$', OrganizationAutocomplete.as_view(), name='organisation-autocomplete',),
    url(r'^person-autocomplete/$', PersonAutocomplete.as_view(), name='person-autocomplete',),
]
