from django.utils.translation import ugettext_lazy as _
from djchoices import ChoiceItem, DjangoChoices


class CourseRunStatus(DjangoChoices):
    Published = ChoiceItem('published', _('Published'))
    Unpublished = ChoiceItem('unpublished', _('Unpublished'))


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
