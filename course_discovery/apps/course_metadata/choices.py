from django.utils.translation import ugettext_lazy as _
from djchoices import ChoiceItem, DjangoChoices


class CourseRunStatus(DjangoChoices):
    Unpublished = ChoiceItem('unpublished', _('Unpublished'))
    LegalReview = ChoiceItem('review_by_legal', _('Awaiting Review from Legal'))
    InternalReview = ChoiceItem('review_by_internal', _('Awaiting Internal Review'))
    Reviewed = ChoiceItem('reviewed', _('Reviewed'))
    Published = ChoiceItem('published', _('Published'))

    INTERNAL_STATUS_TRANSITIONS = (
        InternalReview.value,
        Reviewed.value,
    )

    @classmethod
    def REVIEW_STATES(cls):
        return [cls.LegalReview, cls.InternalReview]


class CourseRunPacing(DjangoChoices):
    # Translators: Instructor-paced refers to course runs that operate on a schedule set by the instructor,
    # similar to a normal university course.
    Instructor = ChoiceItem('instructor_paced', _('Instructor-paced'))
    # Translators: Self-paced refers to course runs that operate on the student's schedule.
    Self = ChoiceItem('self_paced', _('Self-paced'))


class ProgramStatus(DjangoChoices):
    Unpublished = ChoiceItem('unpublished', _('Unpublished'))
    Active = ChoiceItem('active', _('Active'))
    Retired = ChoiceItem('retired', _('Retired'))
    Deleted = ChoiceItem('deleted', _('Deleted'))


class ReportingType(DjangoChoices):
    mooc = ChoiceItem('mooc', 'mooc')
    spoc = ChoiceItem('spoc', 'spoc')
    test = ChoiceItem('test', 'test')
    demo = ChoiceItem('demo', 'demo')
    other = ChoiceItem('other', 'other')


class CertificateType(DjangoChoices):
    Honor = ChoiceItem('honor', _('Honor'))
    Credit = ChoiceItem('credit', _('Credit'))
    Verified = ChoiceItem('verified', _('Verified'))
    Professional = ChoiceItem('professional', _('Professional'))
    Executive_Education = ChoiceItem('executive-education', _('Executive Education'))


class PayeeType(DjangoChoices):
    Platform = ChoiceItem('platform', _('Platform'))
    Organization = ChoiceItem('organization', _('Organization'))
