from django.utils.translation import ugettext_lazy as _
from djchoices import ChoiceItem, DjangoChoices


class PublisherUserRole(DjangoChoices):
    PartnerManager = ChoiceItem('partner_manager', _('Partner Manager'))
    # TODO: ECOM-7289 - Change choice value to `project_coordinator` and create a data migration.
    ProjectCoordinator = ChoiceItem('partner_coordinator', _('Project Coordinator'))
    MarketingReviewer = ChoiceItem('marketing_reviewer', _('Marketing Reviewer'))
    Publisher = ChoiceItem('publisher', _('Publisher'))
    CourseTeam = ChoiceItem('course_team', _('Course Team'))


class CourseStateChoices(DjangoChoices):
    Draft = ChoiceItem('draft', _('Draft'))
    Review = ChoiceItem('review', _('Review'))
    Approved = ChoiceItem('approved', _('Approved'))


class CourseRunStateChoices(CourseStateChoices):
    Published = ChoiceItem('published', _('Published'))
