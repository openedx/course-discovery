import logging

from django.core.management import BaseCommand, CommandError

from course_discovery.apps.course_metadata.models import (
    BackfillCourseRunSlugsConfig, CourseRun, CourseRunStatus, CourseUrlSlug
)

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    """ Management command to add redirects from course run slugs to courses"""

    help = 'Adds published course run slugs to courses if not already present'

    def add_arguments(self, parser):
        parser.add_argument('--all', action='store_true', help='Add redirects from all course run slugs')
        parser.add_argument('-uuids', nargs="*", help='Add redirects from all course run slugs for specific courses')
        parser.add_argument('--args-from-database', action='store_true',
                            help=('Use arguments from the BackfillCourseRunSlugsConfig model instead of the '
                                  'command line.')
                            )

    def handle(self, *args, **options):
        # using mutually exclusive argument groups in management commands is only supported in Django 2.2
        # so use XOR to check manually
        if not bool(options['args_from_database']) ^ (bool(options['uuids']) ^ bool(options['all'])):
            raise CommandError('Invalid arguments')
        options_dict = options
        if options_dict['args_from_database']:
            options_dict = self.get_args_from_database()
        self.add_redirects_from_course_runs(**options_dict)

    def add_course_run_redirect_to_parent_course(self, course_run):
        if course_run.status != CourseRunStatus.Published or course_run.draft:
            return
        existing_slug = CourseUrlSlug.objects.filter(url_slug=course_run.slug,
                                                     partner=course_run.course.partner).first()
        if existing_slug:
            if existing_slug.course.uuid != course_run.course.uuid:
                logger.warning(
                    'Cannot add slug {slug} to course {uuid0}. Slug already belongs to course {uuid1}'.format(
                        slug=course_run.slug,
                        uuid0=course_run.course.uuid,
                        uuid1=existing_slug.course.uuid
                    )
                )
            return

        course_run.course.url_slug_history.create(url_slug=course_run.slug, course=course_run.course,
                                                  partner=course_run.course.partner)

    def add_redirects_from_course_runs(self, **kwargs):
        if kwargs['uuids']:
            for course_run in CourseRun.objects.filter(status=CourseRunStatus.Published,
                                                       course__uuid__in=kwargs['uuids']).all():
                self.add_course_run_redirect_to_parent_course(course_run)
        else:
            for course_run in CourseRun.objects.filter(status=CourseRunStatus.Published).all():
                self.add_course_run_redirect_to_parent_course(course_run)

    def get_args_from_database(self):
        config = BackfillCourseRunSlugsConfig.get_solo()
        return {"all": config.all, "uuids": config.uuids.split()}
