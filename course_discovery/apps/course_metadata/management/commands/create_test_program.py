import logging

from django.core.management import BaseCommand

from course_discovery.apps.core.models import Partner
from course_discovery.apps.course_metadata.choices import CourseRunStatus
from course_discovery.apps.course_metadata.models import CourseRun, Program, ProgramType, Organization
from course_discovery.apps.course_metadata.tests.factories import (
    OrganizationFactory, CorporateEndorsementFactory, EndorsementFactory, ExpectedLearningItemFactory,
    FAQFactory, JobOutlookItemFactory, ProgramFactory, CourseFactory, CourseRunFactory, PartnerFactory
)

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Create program with test data.'

    def handle(self, *args, **options):
        partner = self.create_test_partner()
        self.create_test_program(partner)
        self.create_test_wharton_program(partner)

    def create_test_partner(self):
        partner = Partner.objects.filter(name='test-partner')
        if partner:
            partner.delete()
        logger.info('Creating test-partner')
        partner = PartnerFactory(name='test-partner', marketing_site_url_root=None)
        return partner

    def create_test_program(self, partner):
        program = Program.objects.filter(title='test-program')
        if program:
            program.first().delete()
        logger.info('Creating test-program')
        course = CourseFactory(partner=partner)
        excluded_course_run = CourseRunFactory(course=course)
        ProgramFactory(
            title='test-program',
            partner=partner,
            courses=[course],
            excluded_course_runs=[excluded_course_run],
            authoring_organizations=[OrganizationFactory(partner=partner)],
            credit_backing_organizations=[OrganizationFactory(partner=partner)],
            corporate_endorsements=[CorporateEndorsementFactory()],
            individual_endorsements=[EndorsementFactory(endorser__partner=partner)],
            expected_learning_items=[ExpectedLearningItemFactory()],
            faq=[FAQFactory()],
            job_outlook_items=[JobOutlookItemFactory()]
        )

    def create_test_wharton_program(self, partner):
        program = Program.objects.filter(title='Test Digital Marketing Professional Certificate')
        if program:
            program.first().delete()
        logger.info('Creating Test Wharton Program')
        course_run_keys = [
            'course-v1:Wharton+CustomerCentricityx+3T2016',
            'course-v1:Wharton+DigitalMarketing1.1x+3T2016',
            'course-v1:Wharton+MarketingAnalytics101x+2T2016',
            'course-v1:Wharton+SellingIdeas101x+3T2016'
        ]
        courses = [course_run.course for course_run in CourseRun.objects.filter(key__in=course_run_keys)]
        wharton, _ = Organization.objects.get_or_create(key="Wharton")
        ProgramFactory(
            title="Test Digital Marketing Professional Certificate",
            subtitle="Gain a competitive advantage and learn essential digital marketing skills and strategies in this 4-course program from the top ranked Wharton School of the University of Pennsylvania.",  # pylint: disable=line-too-long
            status=CourseRunStatus.Unpublished,
            type=ProgramType.objects.get(name="Professional Certificate"),
            partner=partner,
            banner_image_url="https://www.edx.org/sites/default/files/prod-land-pg/banner/certificate_banner_1440x326.jpg",  # pylint: disable=line-too-long
            card_image_url="https://www.edx.org/digital-marketing-professional",
            marketing_slug="digital-marketing-professional",
            overview="Make yourself more marketable and put your career in high gear with a Professional Program in Digital Marketing from Wharton. Learn the key marketing skills most in-demand today: omni-channel marketing, marketing analytics, social media strategy and analysis, and data-driven customer-centric approaches to customer retention. Designed by world-renowned marketing professors at the Wharton School, home of one of the top marketing programs in the country, the Professional Certificate in Digital Marketing from Wharton helps you develop the digital marketing skills you need to take advantage of the explosive growth in the marketing industry. Today’s marketers face a “digital skills gap,” and when you earn a Professional Certificate in Digital Marketing from the Wharton School, you’ll be able to help fill it.",  # pylint: disable=line-too-long
            expected_learning_items=[
                ExpectedLearningItemFactory(value="How to leverage new models in business and e-commerce to increase profitability"),  # pylint: disable=line-too-long
                ExpectedLearningItemFactory(value="New techniques in Market Research, including Regression Analysis (modeling cause and effect), Conjoint Analysis (valuing attributes and measuring preference), and Social Media Analytics"),  # pylint: disable=line-too-long
                ExpectedLearningItemFactory(value="How to generate more word of mouth and leverage the power of social media to get your products, ideas, and messages to catch on"),  # pylint: disable=line-too-long
                ExpectedLearningItemFactory(value="How to decide what initial experiments your company should invest in to achieve customer centricity"),  # pylint: disable=line-too-long
                ExpectedLearningItemFactory(value="How to choose metrics to gauge and guide ongoing customer-centric efforts")  # pylint: disable=line-too-long
            ],
            job_outlook_items=[
                JobOutlookItemFactory(value="90% of marketers report suffering from a shortage of digital skills, and only 8% of surveyed companies feel strong in the area of digital marketing. (whitepaper by Grovo)"),  # pylint: disable=line-too-long
                JobOutlookItemFactory(value="In a study conducted by Bullhorn, 64% of recruiters reported a shortage of skilled candidates for available marketing roles"),  # pylint: disable=line-too-long
                JobOutlookItemFactory(value="Employment of marketing managers is projected to grow 9 percent from 2014 to 2024, faster than the average for all occupations. (Bureau of Labor Statistics)"),  # pylint: disable=line-too-long
                JobOutlookItemFactory(value="Career opportunities as a Marketing Manager, Digital Marketing Analyst, or Account Executive, among others Salary range from 56k- 97k per year (*data from Glassdoor)")  # pylint: disable=line-too-long
            ],
            min_hours_effort_per_week=3,
            max_hours_effort_per_week=5,
            authoring_organizations=[wharton],
            courses=courses
        )
