from django.db import models


class InternalUserRole(models.TextChoices):
    PartnerManager = 'partner_manager', 'Partner Manager'  # unused nowadays
    ProjectCoordinator = 'project_coordinator', 'Project Coordinator'
    MarketingReviewer = 'marketing_reviewer', 'Marketing Reviewer'  # unused nowadays
    Publisher = 'publisher', 'Publisher'  # unused nowadays
