import datetime
import logging

import jwt
from django.apps import apps
from django.core.management import BaseCommand
from django.db.models.signals import post_delete, post_save
from edx_rest_api_client.client import EdxRestApiClient
from opaque_keys import InvalidKeyError

from course_discovery.apps.api.cache import api_change_receiver
from course_discovery.apps.core.models import Partner
from course_discovery.apps.course_metadata.choices import CourseRunStatus
from course_discovery.apps.course_metadata.data_loaders.marketing_site import CourseMarketingSiteDataLoader
from course_discovery.apps.publisher.dataloader.create_courses import process_course
from course_discovery.apps.publisher.models import DrupalLoaderConfig

logger = logging.getLogger(__name__)


# Override the CourseMarketingSiteDataLoader to be used specifically
# for this management command instead of refresh_course_metadata.
class DrupalCourseMarketingSiteDataLoader(CourseMarketingSiteDataLoader):
    course_ids = set()
    count = 0

    def __init__(self, partner, api_url, access_token, token_type, max_workers, is_threadsafe, course_ids, **kwargs):
        self.course_ids = course_ids

        super(DrupalCourseMarketingSiteDataLoader, self).__init__(
            partner, api_url, access_token, token_type, max_workers, is_threadsafe, **kwargs
        )

    def _request(self, page):
        """Make a request to the marketing site."""
        logger.info('Processing page %s', page)
        return super(DrupalCourseMarketingSiteDataLoader, self)._request(page)

    def process_node(self, data):
        field_course_end_date = data.get('field_course_end_date')
        # Use as far into the future as possible if there is no end date set
        end_date = (datetime.datetime.fromtimestamp(int(field_course_end_date))
                    if field_course_end_date else datetime.datetime.max)
        is_unarchived = datetime.datetime.now() < end_date
        course_run_key = data.get('field_course_id')

        # Make sure the course run key is one we intend to process and it is unarchived
        if course_run_key in self.course_ids and is_unarchived:
            if not data.get('field_course_uuid'):
                course_run = self.get_course_run(data)

                if course_run:
                    self.update_course_run(course_run, data)
                    if self.get_course_run_status(data) == CourseRunStatus.Published:
                        # Only update the course object with published course about page
                        try:
                            course = self.update_course(course_run.course, data)
                            self.set_subjects(course, data)
                            self.set_authoring_organizations(course, data)
                            logger.info(
                                'Processed course with key [%s] based on the data from courserun [%s]',
                                course.key,
                                course_run.key
                            )

                            # Ingest the course and course runs into Publisher tables via the dataloader methods
                            logger.info('Processing Course [%s] for Publisher tables', course_run_key)
                            process_course(course, True, course_run=course_run)
                        except AttributeError:
                            pass
                    else:
                        logger.info(
                            'Course_run [%s] is unpublished, so the course [%s] related is not updated.',
                            course_run_key,
                            course_run.course.number
                        )
                else:
                    created = False
                    # If the page is not generated from discovery service
                    # shall then attempt to create a course out of it
                    try:
                        course, created = self.get_or_create_course(data)
                        course_run = self.create_course_run(course, data)
                    except InvalidKeyError:
                        logger.error('Invalid course key [%s].', course_run_key)

                    if created:
                        course.canonical_course_run = course_run
                        course.save()

                    # Ingest the course and course runs into Publisher tables via the dataloader methods
                    logger.info('Processing Course [%s] for Publisher tables', course_run_key)
                    process_course(course, True, course_run=course_run)
            else:
                logger.info(
                    'Course_run [%s] has uuid [%s] already on course about page. No need to ingest',
                    data['field_course_id'],
                    data['field_course_uuid']
                )


def execute_loader(loader_class, *loader_args, **loader_kwargs):
    try:
        loader_class(*loader_args, **loader_kwargs).ingest()
    except Exception:  # pylint: disable=broad-except
        logger.exception('%s failed!', loader_class.__name__)


class Command(BaseCommand):
    help = 'Request a set of courses from Drupal to ingest' \
           ' to Course Metadata and Publisher tables if they do not exist'

    def handle(self, *args, **options):
        # We only want to invalidate the API response cache once data loading
        # completes. Disconnecting the api_change_receiver function from post_save
        # and post_delete signals prevents model changes during data loading from
        # repeatedly invalidating the cache.
        for model in apps.get_app_config('course_metadata').get_models():
            for signal in (post_save, post_delete):
                signal.disconnect(receiver=api_change_receiver, sender=model)

        config = DrupalLoaderConfig.get_solo()

        token_type = 'JWT'
        partner = Partner.objects.get(short_code=config.partner_code)
        try:
            access_token, __ = EdxRestApiClient.get_oauth_access_token(
                '{root}/access_token'.format(root=partner.oidc_url_root.strip('/')),
                partner.oidc_key,
                partner.oidc_secret,
                token_type=token_type
            )
        except Exception:
            logger.exception('No access token acquired through client_credential flow.')
            raise
        username = jwt.decode(access_token, verify=False)['preferred_username']
        kwargs = {'username': username} if username else {}

        logger.info('Loading Drupal data for %s with partner codes\n%s',
                    config.partner_code,
                    config.course_run_ids.replace(',', '\n')
                    )

        execute_loader(
            DrupalCourseMarketingSiteDataLoader,
            partner,
            partner.marketing_site_url_root,
            access_token,
            token_type,
            1,  # Make this a constant of 1 for no concurrency
            False,
            set(config.course_run_ids.split(',')),
            **kwargs
        )
