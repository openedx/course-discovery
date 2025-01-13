"""
URLs for the admin autocomplete lookups.
"""

from django.urls import path

from course_discovery.apps.course_metadata.lookups import (
    CollaboratorAutocomplete, CorporateEndorsementAutocomplete, CourseAutocomplete, CourseRunAutocomplete,
    EndorsementAutocomplete, ExpectedLearningItemAutocomplete, FAQAutocomplete, JobOutlookItemAutocomplete,
    OrganizationAutocomplete, PersonAutocomplete, ProgramAutocomplete
)
from course_discovery.apps.course_metadata.views import CourseRunSelectionAdmin

app_name = 'course_metadata'

urlpatterns = [
    path('update_course_runs/<int:pk>/', CourseRunSelectionAdmin.as_view(), name='update_course_runs',),
    path('collaborator-autocomplete/', CollaboratorAutocomplete.as_view(), name='collaborator-autocomplete',),
    path(
        'corporate-endorsement-autocomplete/',
        CorporateEndorsementAutocomplete.as_view(),
        name='corporate-endorsement-autocomplete',
    ),
    path('course-autocomplete/', CourseAutocomplete.as_view(), name='course-autocomplete',),
    path('course-run-autocomplete/', CourseRunAutocomplete.as_view(), name='course-run-autocomplete',),
    path('endorsement-autocomplete/', EndorsementAutocomplete.as_view(), name='endorsement-autocomplete',),
    path(
        'expected-learning-item-autocomplete/',
        ExpectedLearningItemAutocomplete.as_view(),
        name='expected-learning-item-autocomplete',
    ),
    path('faq-autocomplete/', FAQAutocomplete.as_view(), name='faq-autocomplete',),
    path('job-outlook-item-autocomplete/', JobOutlookItemAutocomplete.as_view(), name='job-outlook-item-autocomplete',),
    path('organisation-autocomplete/', OrganizationAutocomplete.as_view(), name='organisation-autocomplete',),
    path('person-autocomplete/', PersonAutocomplete.as_view(), name='person-autocomplete',),
    path('program-autocomplete/', ProgramAutocomplete.as_view(), name='program-autocomplete',),
]
