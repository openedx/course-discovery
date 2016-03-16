import logging

from django.conf import settings
from edx_rest_api_client.client import EdxRestApiClient
from elasticsearch import Elasticsearch, NotFoundError

from au_amber.apps.courses.exceptions import CourseNotFoundError

logger = logging.getLogger(__name__)


class Course(object):
    """
    Course model.

    This model is backed by Elasticsearch.
    """

    # Elasticsearch document type for courses.
    doc_type = 'course'

    # Elasticsearch index where course data is stored
    _index = settings.ELASTICSEARCH['index']

    @classmethod
    def _es_client(cls):
        """ Elasticsearch client. """
        return Elasticsearch(settings.ELASTICSEARCH['host'])

    @classmethod
    def _hit_to_course(cls, hit):
        return Course(hit['_source']['id'], hit['_source'])

    @classmethod
    def all(cls, limit=10, offset=0):
        """
        Return a list of all courses.

        Args:
            limit (int): Maximum number of results to return
            offset (int): Starting index from which to return results

        Returns:
            dict: Representation of data suitable for pagination

        Examples:
            {
                'limit': 10,
                'offset': 0,
                'total': 2,
                'results': [`Course`, `Course`],
            }
        """
        query = {
            'query': {
                'match_all': {}
            }
        }

        return cls.search(query, limit=limit, offset=offset)

    @classmethod
    def get(cls, id):  # pylint: disable=redefined-builtin
        """
        Retrieve a single course.

        Args:
            id (str): Course ID

        Returns:
            Course: The course corresponding to the given ID.

        Raises:
            CourseNotFoundError: if the course is not found.
        """
        try:
            response = cls._es_client().get(index=cls._index, doc_type=cls.doc_type, id=id)
            return cls._hit_to_course(response)
        except NotFoundError:
            raise CourseNotFoundError('Course [{}] was not found in the data store.'.format(id))

    @classmethod
    def search(cls, query, limit=10, offset=0):
        """
        Search the data store for courses.

        Args:
            query (dict): Elasticsearch query used to find courses.
            limit (int): Maximum number of results to return
            offset (int): Index of first result to return

        Returns:
            dict: Representation of data suitable for pagination

        Examples:
            {
                'limit': 10,
                'offset': 0,
                'total': 2,
                'results': [`Course`, `Course`],
            }
        """
        query.setdefault('from', offset)
        query.setdefault('size', limit)
        query.setdefault('sort', {'id': 'asc'})

        logger.debug('Querying [%s]: %s', cls._index, query)
        response = cls._es_client().search(index=cls._index, doc_type=cls.doc_type, body=query)
        hits = response['hits']
        total = hits['total']
        logger.info('Course search returned [%d] courses.', total)

        return {
            'limit': limit,
            'offset': offset,
            'total': total,
            'results': [cls._hit_to_course(hit) for hit in hits['hits']]
        }

    @classmethod
    def refresh(cls, course_id, access_token):
        """
        Refresh the course data from the raw data sources.

        Args:
            course_id (str): Course ID
            access_token (str): OAuth access token

        Returns:
            Course
        """
        client = EdxRestApiClient(settings.ECOMMERCE_API_URL, oauth_access_token=access_token)
        body = client.courses(course_id).get(include_products=True)
        course = Course(course_id, body)
        course.save()
        return course

    @classmethod
    def refresh_all(cls, access_token):
        """
        Refresh all course data.

        Args:
            access_token (str): OAuth access token

        Returns:
            None
        """
        cls.refresh_all_ecommerce_data(access_token)
        cls.refresh_all_course_api_data(access_token)

    @classmethod
    def refresh_all_ecommerce_data(cls, access_token):
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
                Course(body['id']).update(body)

        logger.info('Retrieved %d courses from %s.', count, ecommerce_api_url)

    @classmethod
    def refresh_all_course_api_data(cls, access_token):
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
                Course(body['id']).update(body)

        logger.info('Retrieved %d courses from %s.', count, course_api_url)

    def __init__(self, id, body=None):  # pylint: disable=redefined-builtin
        if not id:
            raise ValueError('Course ID cannot be empty or None.')

        self.id = id
        self.body = body or {}

    def __eq__(self, other):
        """
        Determine if this Course equals another.

        Args:
            other (Course): object with which to compare

        Returns: True iff. the two Course objects have the same `id` value; otherwise, False.

        """
        return self.id is not None \
            and isinstance(other, Course) \
            and self.id == getattr(other, 'id', None) \
            and self.body == getattr(other, 'body', None)

    def __repr__(self):
        return 'Course {id}: {name}'.format(id=self.id, name=self.name)

    @property
    def name(self):
        return self.body.get('name')

    def save(self):
        """ Save the course to the data store. """
        logger.info('Indexing course %s...', self.id)
        self._es_client().index(index=self._index, doc_type=self.doc_type, id=self.id, body=self.body)
        logger.info('Finished indexing course %s.', self.id)

    def update(self, body):
        """ Updates (merges) the data in the index with the provided data.

        Args:
            body (dict): Data to be merged into the index.

        Returns:
            None
        """
        body = {
            'doc': body,
            'doc_as_upsert': True,
        }
        logger.info('Updating course %s...', self.id)
        self._es_client().update(index=self._index, doc_type=self.doc_type, id=self.id, body=body)
        logger.info('Finished updating course %s.', self.id)
