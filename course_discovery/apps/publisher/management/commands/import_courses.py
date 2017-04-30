import logging

from django.core.management import BaseCommand, CommandError
from django.db import connection
from django.shortcuts import get_object_or_404

from course_discovery.apps.core.models import Partner, User
from course_discovery.apps.course_metadata.models import Course as Metadata_Course
from course_discovery.apps.course_metadata.models import Organization
from course_discovery.apps.publisher.choices import CourseRunStateChoices, CourseStateChoices, PublisherUserRole
from course_discovery.apps.publisher.models import Course as Publisher_Course
from course_discovery.apps.publisher.models import CourseRun as Publisher_CourseRun
from course_discovery.apps.publisher.models import Seat as Publisher_Seat
from course_discovery.apps.publisher.models import CourseRunState, CourseState, CourseUserRole, OrganizationExtension

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Import courses into publisher app.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--organization_code',
            action='store',
            dest='organization_code',
            default=None,
            required=True,
            help='The short code for a specific organization to load courses.'

        )

        parser.add_argument(
            '--partner_code',
            action='store',
            dest='partner_code',
            default=None,
            required=True,
            help='Partner code.'
        )

    def handle(self, *args, **options):
        # If a specific partner was indicated, filter down the set

        organization_code = options.get('organization_code')
        partner_code = options.get('partner_code')

        partner = get_object_or_404(
            Partner, short_code=partner_code
        )

        organization = get_object_or_404(
            Organization, key=organization_code, partner=partner
        )

        get_object_or_404(
            OrganizationExtension, organization=organization
        )

        if organization.organization_user_roles.all().count() != 4:
            raise CommandError('Organization User Roles are missing.')

        courses = Metadata_Course.objects.filter(partner=partner, authoring_organizations=organization)
        for course in courses:
            self.get_or_create_course(course)

    def get_or_create_course(self, meta_data_course):

        defaults = {
            'title': meta_data_course.title, 'number': meta_data_course.number,
            'short_description': meta_data_course.short_description,
            'full_description': meta_data_course.full_description,
            'level_type': meta_data_course.level_type,
            'card_image_url': meta_data_course.card_image_url
        }

        course, created = Publisher_Course.objects.update_or_create(
            number__iexact=meta_data_course.number,
            title__iexact=meta_data_course.title,
            defaults=defaults
        )

        if created:
            subjects = meta_data_course.subjects.all()
            subject_count = subjects.count()

            if subject_count == 1:
                course.primary_subject = subjects[0]

            if subject_count == 2:
                course.primary_subject = subjects[0]
                course.secondary_subject = subjects[1]

            if subject_count == 3:
                course.primary_subject = subjects[0]
                course.secondary_subject = subjects[1]
                course.tertiary_subject = subjects[2]

        course.save()

        organization = meta_data_course.authoring_organizations.all().first()

        if created:
            self.assign_roles(course, organization)

        for metadata_course_run in meta_data_course.course_runs.all():
            defaults = {
                'start': metadata_course_run.start, 'end': metadata_course_run.end,
                'enrollment_start': metadata_course_run.enrollment_start, 'enrollment_end': metadata_course_run.enrollment_end,
                'min_effort': metadata_course_run.min_effort, 'max_effort': metadata_course_run.max_effort,
                'language': metadata_course_run.language, 'pacing_type': metadata_course_run.pacing_type,

            }
            course_run, created = Publisher_CourseRun.objects.update_or_create(
                course=course, lms_course_id=metadata_course_run.key, defaults=defaults
            )

            # # # Initialize workflow for Course-run.
            if created:
                CourseRunState.objects.create(
                    course_run=course_run, approved_by_role=PublisherUserRole.ProjectCoordinator,
                    owner_role=PublisherUserRole.Publisher, preview_accepted=True,
                    name=CourseRunStateChoices.Published
                )

            for metadata_seat in metadata_course_run.seats.all():
                defaults = {'price': metadata_seat.price, 'currency': metadata_seat.currency}
                seat, created = Publisher_Seat.objects.update_or_create(
                    course_run=course_run,
                    type=metadata_seat.type,
                    defaults=defaults
                )

        return (course, created)

    def assign_roles(self, course, organization):

        course.organizations.add(organization)

        # add default organization roles into course-user-roles
        for user_role in organization.organization_user_roles.all():
            CourseUserRole.add_course_roles(course, user_role.role, user_role.user)

        CourseState.objects.create(
            course=course, approved_by_role=PublisherUserRole.MarketingReviewer,
            owner_role=PublisherUserRole.MarketingReviewer, marketing_reviewed=True,
            name=CourseStateChoices.Approved
        )
