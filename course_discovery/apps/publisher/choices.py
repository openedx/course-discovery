from djchoices import ChoiceItem, DjangoChoices


class InternalUserRole(DjangoChoices):
    PartnerManager = ChoiceItem('partner_manager', 'Partner Manager')
    ProjectCoordinator = ChoiceItem('project_coordinator', 'Project Coordinator')
    MarketingReviewer = ChoiceItem('marketing_reviewer', 'Marketing Reviewer')
    Publisher = ChoiceItem('publisher', 'Publisher')


class PublisherUserRole(InternalUserRole):
    CourseTeam = ChoiceItem('course_team', 'Course Team')


class CourseStateChoices(DjangoChoices):
    Draft = ChoiceItem('draft', 'Draft')
    Review = ChoiceItem('review', 'Review')
    Approved = ChoiceItem('approved', 'Approved')


class CourseRunStateChoices(CourseStateChoices):
    Published = ChoiceItem('published', 'Published')
