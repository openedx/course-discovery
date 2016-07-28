"""Publisher Wrapper Classes"""
from course_discovery.apps.course_metadata.models import Seat


class BaseWrapper(object):
    def __init__(self, wrapped_obj):
        self.wrapped_obj = wrapped_obj

    def __getattr__(self, attr):
        orig_attr = self.wrapped_obj.__getattribute__(attr)
        if callable(orig_attr):
            def hooked(*args, **kwargs):
                return orig_attr(*args, **kwargs)
        else:
            return orig_attr

    @property
    def fields(self):
        return [field for field in self.wrapped_obj.__dict__.keys() if not field.startswith('_')]


class CourseRunWrapper(BaseWrapper):
    """Decorator for the ``CourseRun`` model."""
    @property
    def partner(self):
        return '/'.join([org.key for org in self.wrapped_obj.course.organizations.all()])

    @property
    def credit_seats(self):
        return [seat for seat in self.wrapped_obj.seats.all() if seat.type == Seat.CREDIT]

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
    def verified_seat(self):
        return [seat for seat in self.wrapped_obj.seats.all() if seat.type == Seat.VERIFIED] or None
