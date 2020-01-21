from djchoices import ChoiceItem, DjangoChoices


class InternalUserRole(DjangoChoices):
    PartnerManager = ChoiceItem('partner_manager', 'Partner Manager')  # unused nowadays
    ProjectCoordinator = ChoiceItem('project_coordinator', 'Project Coordinator')
    MarketingReviewer = ChoiceItem('marketing_reviewer', 'Marketing Reviewer')  # unused nowadays
    Publisher = ChoiceItem('publisher', 'Publisher')  # unused nowadays
