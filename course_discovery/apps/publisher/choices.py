from django.utils.translation import ugettext_lazy as _
from djchoices import DjangoChoices, ChoiceItem


class PublisherUserRole(DjangoChoices):
    PartnerManager = ChoiceItem('partner_manager', _('Partner Manager'))
    PartnerCoordinator = ChoiceItem('partner_coordinator', _('Partner Coordinator'))
    MarketingReviewer = ChoiceItem('marketing_reviewer', _('Marketing Reviewer'))
    Publisher = ChoiceItem('publisher', _('Publisher'))
    CourseTeam = ChoiceItem('course_team', _('Course Team'))
