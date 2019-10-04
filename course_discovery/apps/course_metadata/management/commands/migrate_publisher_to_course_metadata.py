import logging

from django.core.management import BaseCommand, CommandError
from django.db import IntegrityError
from django.utils.translation import ugettext as _

from course_discovery.apps.course_metadata.models import (
    Course, CourseEditor, CourseRun, MigratePublisherToCourseMetadataConfig
)
from course_discovery.apps.course_metadata.utils import publish_to_course_metadata
from course_discovery.apps.publisher.choices import PublisherUserRole
from course_discovery.apps.publisher.models import Course as PublisherCourse
from course_discovery.apps.publisher.models import CourseRun as PublisherCourseRun

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = _('Based on the configuration object, goes through all courses for an organization and '
             'migrates all of the course editors and course data from the publisher tables to the '
             'course metadata tables for use in Publisher Frontend.')

    def handle(self, *args, **options):
        config = MigratePublisherToCourseMetadataConfig.get_solo()
        orgs = config.orgs.all()
        if not orgs:
            logger.error(_(
                'No organizations were defined. Please add organizations to the '
                'MigratePublisherToCourseMetadataConfig model.'
            ))
            raise CommandError(_('No organizations were defined.'))

        exception_course_run_keys = []
        partner = config.partner
        for org in orgs:
            org_runs = CourseRun.objects.filter(course__authoring_organizations__in=[org])
            key_queryset = org_runs.values_list('key', flat=True)
            matched_runs = PublisherCourseRun.objects.filter(lms_course_id__in=key_queryset)  # in both CM and Pub

            for course_run in matched_runs.order_by('modified'):
                try:
                    # set fail_on_url_slug to false so this doesn't fail in the case where one publisher course
                    # corresponds to 2 course_metadata courses
                    publish_to_course_metadata(partner, course_run, create_official=False, fail_on_url_slug=False)
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
                publisher_courses = PublisherCourse.objects.filter(number=course_number)
                if not publisher_courses.exists():
                    logger.info(
                        _('Course with course number [{course_number}] is not a valid course number for any '
                          'existing course in the Publisher tables. As such, there can be no Course User Roles to '
                          'move to Course Editors.').format(course_number=course_number)
                    )
                    continue
                for publisher_course in publisher_courses:
                    for user_role in publisher_course.course_user_roles.filter(role=PublisherUserRole.CourseTeam):
                        # Using update_or_create in case a course has multiple authoring organizations and the course
                        # shows up more than once.
                        CourseEditor.objects.update_or_create(course=discovery_course, user=user_role.user)

        # Fail the job to help increase visibility of course runs that could not be published to course metadata.
        if exception_course_run_keys:
            raise CommandError(
                _('The following Publisher course run keys failed to publish to Course Metadata: '
                  '{exception_course_run_keys}.').format(exception_course_run_keys=exception_course_run_keys)
            )
