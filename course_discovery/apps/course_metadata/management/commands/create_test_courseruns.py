import logging
import os
from django.core.management import BaseCommand

from course_discovery.apps.core.models import Partner
from course_discovery.apps.course_metadata.models import Organization, CourseRunType
from course_discovery.apps.course_metadata.tests.factories import (
    CorporateEndorsementFactory, CourseFactory, CourseRunFactory, EndorsementFactory, ExpectedLearningItemFactory,
    FAQFactory, JobOutlookItemFactory, OrganizationFactory, PersonFactory, ProgramFactory, SubjectFactory
)

logger = logging.getLogger(__name__)

base_course_url = os.environ.get(
    'SOCIAL_AUTH_EDX_OAUTH2_URL_ROOT', 'http://edx.devstack.lms:18000')


class Command(BaseCommand):
    help = 'Create Course and CourseRuns with factory data.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--partner_code',
            action='store',
            dest='partner_code',
            default='edx',
            help='The short code for a specific partner to which test data will be added. defaults to edx.'
        )

    def handle(self, *args, **options):
        partner_code = options.get('partner_code')
        logger.info('Searching for partner by code: {}'.format(partner_code))

        partner = Partner.objects.get(short_code=partner_code)

        # Update partner URL to be usable with dev environment:
        if (partner.courses_api_url != base_course_url):
            partner.courses_api_url = base_course_url
            logger.info(
                'Changing base partner URL for courses to {}'.format(base_course_url))
            partner.save()

        self.create_test_courseruns(partner)

    def create_test_courseruns(self, partner):
        logger.info('Creating test Course with 2 CourseRuns')

        org = None
        try:
            org = Organization.objects.get(partner=partner)
        except Organization.DoesNotExist:
            org = OrganizationFactory(partner=partner)
            org.save()

        subject = SubjectFactory(partner=partner)
        verified_and_audit_type = CourseRunType.objects.get(slug='verified-audit')

        course = CourseFactory(
            partner=partner)
        course.subjects.add(subject)
        course.save()
        
        course_run_1 = CourseRunFactory(course=course, type=verified_and_audit_type)
        course_run_2 = CourseRunFactory(course=course, type=verified_and_audit_type)

        logger.info('Using Partner: {}'.format(partner))
        logger.info('Using Org: {}'.format(org))
        logger.info('Created new course: {}'.format(course))
        logger.info('Created new course run: {}'.format(course_run_1))
        logger.info('Created new course run: {}'.format(course_run_2))
