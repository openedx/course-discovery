import logging
import re

from django.core.exceptions import ObjectDoesNotExist
from django.core.management import BaseCommand, CommandError
from django.utils.translation import ugettext as _

from course_discovery.apps.course_metadata.models import CourseUrlRedirect, CourseUrlSlug, RemoveRedirectsConfig

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    """ Management command to remove redirects (non-canonical urls) from courses, effectively removing those urls
    from the site for the next prospectus build
    ./manage.py remove_redirects_from_courses --remove_all OR
    ./manage.py remove_redirects_from_courses -url_paths /course/slug-0 /some/other/path ..."""

    help = 'Remove redirects from courses'

    def add_arguments(self, parser):
        parser.add_argument('--remove_all', action='store_true', help=_('Remove all redirects to all courses'))
        parser.add_argument('-url_paths', nargs="*", help=_('Redirects to remove'))
        parser.add_argument('--args-from-database', action='store_true',
                            help=_('Use arguments from the RemoveRedirectsConfig model instead of the command line.')
                            )

    def handle(self, *args, **options):
        # using mutually exclusive argument groups in management commands is only supported in Django 2.2
        # so use XOR to check manually
        if not bool(options['args_from_database']) ^ (bool(options['url_paths']) ^ bool(options['remove_all'])):
            raise CommandError(_('Invalid arguments'))
        options_dict = options
        if options_dict['args_from_database']:
            options_dict = self.get_args_from_database()
        if options_dict['url_paths']:
            self.remove_redirects(options_dict['url_paths'])
            return
        if options_dict['remove_all']:
            self.remove_all_redirects()

    def remove_all_redirects(self):
        CourseUrlRedirect.objects.all().delete()
        # keep active url slug
        CourseUrlSlug.objects.filter(is_active=False, is_active_on_draft=False).delete()

    def remove_redirects(self, url_paths):
        standard_course_url_regex = re.compile('^/?course/([^/]*)$')
        for url_path in url_paths:
            matched = standard_course_url_regex.match(url_path)
            if matched:
                url_slug = matched.group(1)
                try:
                    url_slug_object = CourseUrlSlug.objects.get(url_slug=url_slug)
                    if url_slug_object.is_active or url_slug_object.is_active_on_draft:
                        logger.warning(_('Cannot remove active url_slug {url_slug}').format(url_slug=url_slug))
                        continue
                    url_slug_object.delete()
                except ObjectDoesNotExist:
                    logger.info(_('Path /course/{url_slug} not in use, nothing to delete').format(url_slug=url_slug))
                continue
            # if not of the form /course/<slug>, the path would be stored in CourseUrlRedirects
            deleted = CourseUrlRedirect.objects.filter(value=url_path).delete()
            if deleted[0] == 0:
                logger.info(_('Path {url_path} not in use, nothing to delete').format(url_path=url_path))

    def get_args_from_database(self):
        config = RemoveRedirectsConfig.get_solo()
        return {"remove_all": config.remove_all, "url_paths": config.url_paths.split()}
