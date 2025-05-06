"""Publisher Wrapper Classes"""
from datetime import timedelta

from django.contrib.contenttypes.models import ContentType
from django.utils.translation import ugettext_lazy as _

from course_discovery.apps.course_metadata.choices import CourseRunPacing
from course_discovery.apps.publisher.choices import PublisherUserRole
from course_discovery.apps.publisher.models import Course, Seat
from course_discovery.apps.publisher_comments.models import Comments, CommentTypeChoices


class BaseWrapper(object):
    def __init__(self, wrapped_obj):
        self.wrapped_obj = wrapped_obj

    def __getattr__(self, attr):
        orig_attr = self.wrapped_obj.__getattribute__(attr)
        if callable(orig_attr):
            def hooked(*args, **kwargs):
                return orig_attr(*args, **kwargs)
            return hooked
        else:
            return orig_attr


class CourseRunWrapper(BaseWrapper):
    """Decorator for the ``CourseRun`` model."""

    # course team status
    Draft = _('Draft')
    SubmittedForProjectCoordinatorReview = _('Submitted for Project Coordinator Review')
    AwaitingCourseTeamReview = _('Awaiting Course Team Review')

    # internal user status
    NotAvailable = _('N/A')
    AwaitingProjectCoordinatorReview = _('Awaiting Project Coordinator Review')
    ApprovedByProjectCoordinator = _('Approved by Project Coordinator')

    @property
    def title(self):
        return self.wrapped_obj.course.title

    @property
    def is_seat_version(self):
        return self.wrapped_obj.course.version == Course.SEAT_VERSION

    @property
    def is_entitlement_version(self):
        return self.wrapped_obj.course.version == Course.ENTITLEMENT_VERSION

    @property
    def is_authored_in_studio(self):
        if self.wrapped_obj.lms_course_id:
            return True

        return False

    @property
    def mdc_submission_due_date(self):
        if self.wrapped_obj.start:
            return self.wrapped_obj.start - timedelta(days=10)

        return None
