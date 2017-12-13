import logging

from django.core.management import BaseCommand

from course_discovery.apps.core.models import Partner
from course_discovery.apps.course_metadata.models import Program
from course_discovery.apps.course_metadata.tests.factories import (
    CorporateEndorsementFactory, CourseFactory, CourseRunFactory, EndorsementFactory, ExpectedLearningItemFactory,
    FAQFactory, JobOutlookItemFactory, OrganizationFactory, PersonFactory, ProgramFactory
)

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Create program with test data.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--partner_code',
            action='store',
            dest='partner_code',
            required=True,
            help='The short code for a specific partner to which a test program will be added.'
        )

    def handle(self, *args, **options):
        partner_code = options.get('partner_code')
        partner = Partner.objects.get(short_code=partner_code)
        self.create_test_program(partner)

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
            job_outlook_items=[JobOutlookItemFactory()],
            instructor_ordering=[PersonFactory()],
        )
