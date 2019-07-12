import logging

from django.contrib.auth import get_user_model
from django.core.management import BaseCommand, CommandError
from django.db import IntegrityError
from django.utils.translation import ugettext as _

from course_discovery.apps.course_metadata.models import (
    Course, CourseEditor, MigratePublisherToCourseMetadataConfig, Organization
)
from course_discovery.apps.course_metadata.utils import publish_to_course_metadata
from course_discovery.apps.publisher.choices import PublisherUserRole
from course_discovery.apps.publisher.models import Course as PublisherCourse
from course_discovery.apps.publisher.models import CourseUserRole

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = _('Based on the configuration object, goes through all courses for an organization and '
             'migrates all of the course editors and course data from the publisher tables to the '
             'course metadata tables for use in Publisher Frontend.')

    def handle(self, *args, **options):
        config = MigratePublisherToCourseMetadataConfig.get_solo()

        if not config.org_keys:
            logger.error(_(
                'No organization keys were defined. Please add organization keys to the '
                'MigratePublisherToCourseMetadataConfig model.'
            ))
            raise CommandError(_('No organization keys were defined.'))

        exception_org_keys = []
        exception_course_run_keys = []
        UserModel = get_user_model()
        org_keys = config.org_keys.split(',')
        for org_key in org_keys:
            org_key = org_key.strip()
            try:
                org = Organization.objects.get(key=org_key)
            except Organization.DoesNotExist:
                logger.exception(
                    _('Organization key [{org_key}] is not a valid key for any existing organization.').format(
                        org_key=org_key
                    )
                )
                exception_org_keys.append(org_key)
                continue

            for publisher_course in PublisherCourse.objects.filter(organizations__in=[org]):
                for course_run in publisher_course.course_runs.all():
                    partner = org.partner
                    try:
                        publish_to_course_metadata(partner, course_run, draft=True)
                    except IntegrityError as e:
                        logger.exception(
                            _('Error publishing course run [{course_run_key}] to Course Metadata: {error}. '
                              'This may have caused the corresponding course to not be published as well.').format(
                                course_run_key=course_run.lms_course_id, error=str(e)
                            )
                        )
                        exception_course_run_keys.append(course_run.lms_course_id)
                        continue

            for discovery_course in Course.everything.filter(authoring_organizations__in=[org], draft=True):
                course_number = discovery_course.key.split('+')[-1]
                try:
                    publisher_course = PublisherCourse.objects.get(number=course_number)
                except PublisherCourse.DoesNotExist:
                    logger.exception(
                        _('Course with course number [{course_number}] is not a valid course number for any '
                          'existing course in the Publisher tables. As such, there can be no Course User Roles to '
                          'move to Course Editors.').format(course_number=course_number)
                    )
                    continue
                for user_role in CourseUserRole.objects.filter(
                    course_id=publisher_course, role=PublisherUserRole.CourseTeam
                ):
                    user = UserModel.objects.get(pk=user_role.user_id)
                    # Using update_or_create in case a course has multiple authoring organizations and the course
                    # shows up more than once.
                    CourseEditor.objects.update_or_create(course=discovery_course, user=user)

        # Fail the job to help increase visibility of orgs that were not valid.
        if exception_org_keys or exception_course_run_keys:
            raise CommandError(
                _('The following organization keys were not valid for any exisiting organizations: '
                  '{exception_org_keys}.\nThe following Publisher course run keys failed to publish to '
                  'Course Metadata: {exception_course_run_keys}.').format(
                    exception_org_keys=exception_org_keys, exception_course_run_keys=exception_course_run_keys
                )
            )
