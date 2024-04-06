from django.db import models
from django.utils.translation import gettext_lazy as _


class CourseRunStatus(models.TextChoices):
    Unpublished = 'unpublished', _('Unpublished')
    LegalReview = 'review_by_legal', _('Awaiting Review from Legal')
    InternalReview = 'review_by_internal', _('Awaiting Internal Review')
    Reviewed = 'reviewed', _('Reviewed')
    Published = 'published', _('Published')

    @classmethod
    def INTERNAL_STATUS_TRANSITIONS(cls):
        return (cls.InternalReview.value, cls.Reviewed.value)

    @classmethod
    def REVIEW_STATES(cls):
        return [cls.LegalReview.value, cls.InternalReview.value]


class CourseRunPacing(models.TextChoices):
    # Translators: Instructor-paced refers to course runs that operate on a schedule set by the instructor,
    # similar to a normal university course.
    Instructor = 'instructor_paced', _('Instructor-paced')
    # Translators: Self-paced refers to course runs that operate on the student's schedule.
    Self = 'self_paced', _('Self-paced')


class ProgramStatus(models.TextChoices):
    Unpublished = 'unpublished', _('Unpublished')
    Active = 'active', _('Active')
    Retired = 'retired', _('Retired')
    Deleted = 'deleted', _('Deleted')


class ReportingType(models.TextChoices):
    mooc = 'mooc', _('mooc')
    spoc = 'spoc', _('spoc')
    test = 'test', _('test')
    demo = 'demo', _('demo')
    other = 'other', _('other')


class CertificateType(models.TextChoices):
    Honor = 'honor', _('Honor')
    Credit = 'credit', _('Credit')
    Verified = 'verified', _('Verified')
    Professional = 'professional', _('Professional')
    Executive_Education = 'executive-education', _('Executive Education')
    Paid_Executive_Education = 'paid-executive-education', _('Paid Executive Education')
    Unpaid_Executive_Education = 'unpaid-executive-education', _('Unpaid Executive Education')
    Paid_Bootcamp = 'paid-bootcamp', _('Paid Bootcamp')
    Unpaid_Bootcamp = 'unpaid-bootcamp', _('Unpaid Bootcamp')


class PayeeType(models.TextChoices):
    Platform = 'platform', _('Platform')
    Organization = 'organization', _('Organization')


class CourseLength(models.TextChoices):
    Short = 'short', _('Short')
    Medium = 'medium', _('Medium')
    Long = 'long', _('Long')


class ExternalProductStatus(models.TextChoices):
    """
    The statuses for external product lines.
    """
    Archived = 'archived', _('Archived')
    Published = 'published', _('Published')


class ExternalCourseMarketingType(models.TextChoices):
    """
    Course Types for external courses marketing type.
    """
    ShortCourse = 'short_course', _('Short Course')
    Sprint = 'sprint', _('Sprint')
    CourseStack = 'course_stack', _('Course Stack')


class CourseRunRestrictionType(models.TextChoices):
    CustomB2BEnterprise = 'custom-b2b-enterprise', _('Custom B2B Enterprise')
    CustomB2C = 'custom-b2c', _('Custom B2C')
