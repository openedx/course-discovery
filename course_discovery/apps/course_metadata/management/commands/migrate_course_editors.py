import logging

from django.contrib.auth import get_user_model
from django.core.management import BaseCommand, CommandError
from django.utils.translation import ugettext as _
from course_discovery.apps.course_metadata.models import Course, CourseEditor, MigrateCourseEditorsConfig, Organization
from course_discovery.apps.publisher.choices import PublisherUserRole
from course_discovery.apps.publisher.models import Course as PublisherCourse
from course_discovery.apps.publisher.models import CourseUserRole

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = _('Based on the configuration object, migrates all of the course editors for an organization '
             'from publisher tables to course metadata tables for use in Publisher Frontend.')

    def handle(self, *args, **options):
        config = MigrateCourseEditorsConfig.get_solo()

        if not config.org_keys:
            logger.error(_(
                'No organization keys were defined. Please add organization keys to the MigrateCourseEditorsConfig '
                'model.'
            ))
            raise CommandError(_('No organization keys were defined.'))

        exception_org_keys = []
        UserModel = get_user_model()
        org_keys = config.org_keys.split(',')
        for org_key in org_keys:
            org_key = org_key.strip()
            try:
                org = Organization.objects.get(key=org_key)
            except Organization.DoesNotExist:
                logger.exception(_(
                    'Organization key [{org_key}] is not a valid key for any existing organization.'.format(
                        org_key=org_key
                    )
                ))
                exception_org_keys.append(org_key)
                continue
            for discovery_course in Course.objects.filter(authoring_organizations__in=[org]):
                course_number = discovery_course.key.split('+')[-1]
                try:
                    publisher_course = PublisherCourse.objects.get(number=course_number)
                except PublisherCourse.DoesNotExist:
                    logger.exception(_(
                        'Course with course number [{course_number}] is not a valid course number for any '
                        'existing course in the Publisher tables. As such, there can be no Course User Roles to '
                        'move to Course Editors.'.format(course_number=course_number)
                    ))
                    continue
                for user_role in CourseUserRole.objects.filter(
                    course_id=publisher_course, role=PublisherUserRole.CourseTeam
                ):
                    user_id = user_role.user_id
                    user = UserModel.objects.get(pk=user_id)
                    # We prefer linking to draft courses because editors make sense in the context of drafts, but we
                    # are choosing to default to the official version so we do not have to create the draft world
                    # for a course as part of this command. When the draft world is eventually created, we will
                    # move the editors from the official version to the draft version.
                    editor_course = discovery_course.draft_version or discovery_course
                    # Using update_or_create in case a course has multiple authoring organizations and the course
                    # shows up more than once.
                    CourseEditor.objects.update_or_create(course=editor_course, user=user)

        # Fail the job to help increase visibility of orgs that were not valid.
        if exception_org_keys:
            raise CommandError(_(
                'The following organization keys were not valid for any exisiting organizations: '
                '{exception_org_keys}.'.format(exception_org_keys=exception_org_keys)
            ))
