"""
URLs for the admin autocomplete lookups.
"""

from django.urls import path

from course_discovery.apps.course_metadata.lookups import (
    CourseAutocomplete, CourseRunAutocomplete, OrganizationAutocomplete, PersonAutocomplete, ProgramAutocomplete
)
from course_discovery.apps.course_metadata.views import CourseRunSelectionAdmin

app_name = 'course_metadata'

urlpatterns = [
    path('update_course_runs/<int:pk>/', CourseRunSelectionAdmin.as_view(), name='update_course_runs',),
    path('course-autocomplete/', CourseAutocomplete.as_view(), name='course-autocomplete',),
    path('course-run-autocomplete/', CourseRunAutocomplete.as_view(), name='course-run-autocomplete',),
    path('organisation-autocomplete/', OrganizationAutocomplete.as_view(), name='organisation-autocomplete',),
    path('person-autocomplete/', PersonAutocomplete.as_view(), name='person-autocomplete',),
    path('program-autocomplete/', ProgramAutocomplete.as_view(), name='program-autocomplete',),
]
