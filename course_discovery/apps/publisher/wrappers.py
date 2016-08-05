"""Publisher Wrapper Classes"""
from django.utils.translation import ugettext_lazy as _
from course_discovery.apps.publisher.models import Seat, State

CHANGE_STATE_BUTTON_VALUES = {
    State.DRAFT: {'value': State.NEEDS_REVIEW, 'text': _('Send For Review')},
    State.NEEDS_REVIEW: {'value': State.NEEDS_FINAL_APPROVAL, 'text': _('Send For Final Approval')},
    State.NEEDS_FINAL_APPROVAL: {'value': State.FINALIZED, 'text': _('Finalize')},
    State.FINALIZED: {'value': State.PUBLISHED, 'text': _('Publish')}
}


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
    @property
    def title(self):
        return self.wrapped_obj.course.title

    @property
    def partner(self):
        return '/'.join([org.key for org in self.wrapped_obj.course.organizations.all()])

    @property
    def credit_seat(self):
        credit_seat = [seat for seat in self.wrapped_obj.seats.all() if seat.type == Seat.CREDIT]
        if not credit_seat:
            return None
        return credit_seat[0]

    @property
    def non_credit_seats(self):
        return [seat for seat in self.wrapped_obj.seats.all() if seat.type != Seat.CREDIT]

    @property
    def video_languages(self):
        return ', '.join([lang.name for lang in self.wrapped_obj.transcript_languages.all()])

    @property
    def persons(self):
        return ', '.join([person.name for person in self.wrapped_obj.staff.all()])

    @property
    def verified_seat_price(self):
        seats = [seat for seat in self.wrapped_obj.seats.all() if seat.type == Seat.VERIFIED]
        if not seats:
            return None
        return seats[0].price

    @property
    def number(self):
        return self.wrapped_obj.course.number

    @property
    def short_description(self):
        return self.wrapped_obj.course.short_description

    @property
    def level_type(self):
        return self.wrapped_obj.course.level_type

    @property
    def full_description(self):
        return self.wrapped_obj.course.full_description

    @property
    def expected_learnings(self):
        return self.wrapped_obj.course.expected_learnings

    @property
    def prerequisites(self):
        return self.wrapped_obj.course.prerequisites

    @property
    def learner_testimonial(self):
        return self.wrapped_obj.course.learner_testimonial

    @property
    def syllabus(self):
        return self.wrapped_obj.course.syllabus

    @property
    def subjects(self):
        return [
            self.wrapped_obj.course.primary_subject,
            self.wrapped_obj.course.secondary_subject,
            self.wrapped_obj.course.tertiary_subject
        ]

    @property
    def subject_names(self):
        return ', '.join([subject.name for subject in self.subjects if subject])

    @property
    def course_type(self):
        seats_types = [seat.type for seat in self.wrapped_obj.seats.all()]
        if [Seat.AUDIT] == seats_types:
            return Seat.AUDIT
        if Seat.CREDIT in seats_types and Seat.VERIFIED in seats_types:
            return Seat.CREDIT
        if Seat.VERIFIED in seats_types:
            return Seat.VERIFIED
        if Seat.PROFESSIONAL in seats_types:
            return Seat.PROFESSIONAL
        return Seat.AUDIT

    @property
    def organization_key(self):
        organizations = self.wrapped_obj.course.organizations.all()
        if not organizations:
            return None
        return organizations[0].key

    @property
    def workflow_state(self):
        return self.wrapped_obj.current_state

    @property
    def change_state_button(self):
        return CHANGE_STATE_BUTTON_VALUES.get(self.wrapped_obj.state.name)
