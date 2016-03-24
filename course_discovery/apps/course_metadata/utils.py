import datetime
import logging

from django.conf import settings
from edx_rest_api_client.client import EdxRestApiClient

from course_discovery.apps.course_metadata.config import COURSES_INDEX_CONFIG

logger = logging.getLogger(__name__)


class ElasticsearchUtils(object):
    @classmethod
    def create_alias_and_index(cls, es, alias):
        logger.info('Making sure alias [%s] exists...', alias)

        if es.indices.exists_alias(name=alias):
            # If the alias exists, and points to an open index, we are all set.
            logger.info('...alias exists.')
        else:
            # Create an index with a unique (timestamped) name
            timestamp = datetime.datetime.utcnow().strftime("%Y%m%d%H%M%S")
            index = '{alias}_{timestamp}'.format(alias=alias, timestamp=timestamp)
            es.indices.create(index=index, body=COURSES_INDEX_CONFIG)
            logger.info('...index [%s] created.', index)

            # Point the alias to the new index
            body = {
                'actions': [
                    {'remove': {'alias': alias, 'index': '*'}},
                    {'add': {'alias': alias, 'index': index}},
                ]
            }
            es.indices.update_aliases(body)
            logger.info('...alias updated.')


class CourseRunRefreshUtils(object):
    """ Course refresh utility. """
    @classmethod
    def refresh_all(cls, access_token):
        """
        Refresh course run data from the raw data sources for all courses.

        Args:
            access_token (str): Access token used to connect to data sources.

        Returns:
            None
        """
        cls._refresh_lms_all(access_token)
        cls._refresh_ecommerce_all(access_token)

    @classmethod
    def _refresh_ecommerce_all(cls, access_token):
        """
        Refresh course run data from ecommerce for all courses.

        Args:
            access_token (str): Access token used to connect to data sources.

        Returns:
            None
        """
        ecommerce_api_url = settings.ECOMMERCE_API_URL
        client = EdxRestApiClient(ecommerce_api_url, oauth_access_token=access_token)
        count = None
        page = 1

        logger.info('Refreshing ecommerce data from %s....', ecommerce_api_url)

        while page:
            response = client.courses().get(include_products=True, page=page, page_size=50)
            count = response['count']
            results = response['results']
            logger.info('Retrieved %d courses...', len(results))

            if response['next']:
                page += 1
            else:
                page = None

            for body in results:
                cls._update_ecommerce_course(body)

        logger.info('Retrieved %d courses from %s.', count, ecommerce_api_url)

    @classmethod
    def _refresh_drupal_all(cls, access_token):
        """
        Refresh course run data from drupal for all courses.

        Args:
            access_token (str): Access token used to connect to data sources.

        Returns:
            None
        """
        pass

    @classmethod
    def _refresh_lms_all(cls, access_token):
        """
        Refresh course run data from lms for all courses.

        Args:
            access_token (str): Access token used to connect to data sources.

        Returns:
            None
        """
        course_api_url = settings.COURSES_API_URL
        client = EdxRestApiClient(course_api_url, oauth_access_token=access_token)

        count = None
        page = 1

        logger.info('Refreshing course api data from %s....', course_api_url)

        while page:
            # TODO Update API to not require username?
            response = client.courses().get(page=page, page_size=50, username='ecommerce_worker')
            count = response['pagination']['count']
            results = response['results']
            logger.info('Retrieved %d courses...', len(results))

            if response['pagination']['next']:
                page += 1
            else:
                page = None

            for body in results:
                cls._update_lms_course(body)

        logger.info('Retrieved %d courses from %s.', count, course_api_url)

    @classmethod
    def _update_lms_course(cls, body):
        """
        Create or update the course run and course data with lms data.

        Args:
            body (dict): Course data

        Returns:
            None
        """
        course_run_key = body['id']
        course_key = "{org}+{number}".format(org=body['org'], number=body['number'])

        course_run, created = CourseRun.get_or_create(key=course_run_key)
        course, created = Course.get_or_create(key=course_key)

        # This is where we will set all of the lms data we want to store.
        course_run.course = course

        course_run.save()
        course.save()

    @classmethod
    def _update_ecommerce_course(cls, body):
        """
        Create or update the course run seat data with ecommerce data.

        Args:
            body (dict): Course data

        Returns:
            None
        """
        course_run_key = body['id']

        course_run = CourseRun.get(key=course_run_key)

        # This is where we will set the new seat data
        course_run.seat_set.clear()

        for seat in body['products']:
            if seat['structure'] != 'child':
                continue

            price = float(seat['price'])
            currency_iso_code = 'USD'
            certificate_type = 'audit'
            upgrade_deadline = None
            credit_provider = None
            credit_hours = None

            # Iterate over attributes and extract important values
            for attr in seat['attribute_values']:
                if attr['name'] == 'certificate_type':
                    certificate_type = attr['value']
                if attr['name'] == 'credit_hours':
                    credit_hours = attr['value']
                if attr['name'] == 'credit_provider':
                    credit_provider = attr['value']

            if seat['expires'] is not None:
                upgrade_deadline = datetime.datetime.strptime(seat['expires'], "%Y%m%dT%H%M%SZ")

            # course_run.seat_set.add(
            #     Seat(
            #         external_ecommerce_id=seat['id'],
            #         price=price,
            #         currency_iso_code=currency_iso_code,
            #         type=certificate_type,
            #         upgrade_deadline=upgrade_deadline,
            #         credit_provider=credit_provider,
            #         credit_hours=credit_hours
            #     )
            # )
