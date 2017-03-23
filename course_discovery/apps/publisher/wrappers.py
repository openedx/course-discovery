"""Publisher Wrapper Classes"""
from datetime import timedelta

from course_discovery.apps.course_metadata.choices import CourseRunPacing
from course_discovery.apps.publisher.models import Seat


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
    def transcript_languages(self):
        return ', '.join([lang.name for lang in self.wrapped_obj.transcript_languages.all()])

    @property
    def persons(self):
        return ', '.join([person.full_name for person in self.wrapped_obj.staff.all()])

    @property
    def verified_seat_price(self):
        seat = self.wrapped_obj.seats.filter(type=Seat.VERIFIED).first()
        if not seat:
            return None
        return seat.price

    @property
    def verified_seat_expiry(self):
        seat = self.wrapped_obj.seats.filter(type=Seat.VERIFIED).first()
        if not seat:
            return None
        return seat.upgrade_deadline

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
        organization = self.wrapped_obj.course.organizations.first()
        if not organization:
            return None
        return organization.key

    @property
    def organization_name(self):
        organization = self.wrapped_obj.course.organizations.first()
        if not organization:
            return None
        return organization.name

    @property
    def is_authored_in_studio(self):
        if self.wrapped_obj.lms_course_id:
            return True

        return False

    @property
    def is_multiple_partner_course(self):
        organizations_count = self.wrapped_obj.course.organizations.all().count()
        if organizations_count > 1:
            return True

        return False

    @property
    def is_self_paced(self):
        if self.wrapped_obj.pacing_type == CourseRunPacing.Self:
            return True

        return False

    @property
    def mdc_submission_due_date(self):
        if self.wrapped_obj.start:
            return self.wrapped_obj.start - timedelta(days=10)

        return None

    @property
    def verification_deadline(self):
        return self.wrapped_obj.course.verification_deadline

    @property
    def keywords(self):
        return self.wrapped_obj.course.keywords_data

    @property
    def is_seo_review(self):
        return self.wrapped_obj.course.is_seo_review

    @property
    def course_team_admin(self):
        return self.wrapped_obj.course.course_team_admin

    @property
    def course_image(self):
        if self.wrapped_obj.course.image:
            return self.wrapped_obj.course.image.thumbnail.url

    @property
    def course_staff(self):
        staff_list = []
        for staff in self.wrapped_obj.staff.all():
            staff_dict = {
                'full_name': staff.full_name,
                'image_url': staff.get_profile_image_url,
                'profile_url': staff.profile_url
            }

            if hasattr(staff, 'position'):
                staff_dict.update({
                    'position': staff.position.title,
                    'organization': staff.position.organization_name,
                })

            staff_list.append(staff_dict)

        return staff_list
