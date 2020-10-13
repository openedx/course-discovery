import json
import logging

import pytest
import responses
from django.conf import settings
from haystack import connections as haystack_connections

from course_discovery.apps.core.utils import ElasticsearchUtils
from course_discovery.apps.course_metadata.models import Course, CourseRun, Person

logger = logging.getLogger(__name__)


@pytest.mark.usefixtures('haystack_default_connection')
class ElasticsearchTestMixin:
    def setUp(self):
        super().setUp()
        self.index = settings.HAYSTACK_CONNECTIONS['default']['INDEX_NAME']
        connection = haystack_connections['default']
        self.es = connection.get_backend().conn

    def refresh_index(self):
        """
        Refreshes an index.

        https://www.elastic.co/guide/en/elasticsearch/reference/current/indices-refresh.html
        """
        ElasticsearchUtils.refresh_index(self.es, self.index)

    def reindex_course_runs(self, course):
        index = haystack_connections['default'].get_unified_index().get_index(CourseRun)
        for course_run in course.course_runs.all():
            index.update_object(course_run)

    def reindex_courses(self, program):
        index = haystack_connections['default'].get_unified_index().get_index(Course)
        for course in program.courses.all():
            index.update_object(course)
            self.reindex_course_runs(course)

    def reindex_people(self, person):
        index = haystack_connections['default'].get_unified_index().get_index(Person)
        index.update_object(person)


class LMSAPIClientMixin:
    def mock_api_access_request(self, lms_url, user, status=200, api_access_request_overrides=None):
        """
        Mock the api access requests endpoint response of the LMS.
        """
        data = {
            'count': 2,
            'num_pages': 1,
            'current_page': 1,
            'results':
                [
                    dict(
                        {
                            'id': 1,
                            'created': '2017-09-25T08:37:05.872566Z',
                            'modified': '2017-09-25T08:37:47.412496Z',
                            'user': 1,
                            'status': 'approved',
                            'website': 'https://example.com/',
                            'reason': 'Example Reason',
                            'company_name': 'Test Company',
                            'company_address': 'Example Address',
                            'site': 1,
                            'contacted': True
                        },
                        **(api_access_request_overrides or {})
                    )
                ],
            'next': None,
            'start': 0,
            'previous': None
        }

        responses.add(
            responses.GET,
            lms_url.rstrip('/') + f'/api-admin/api/v1/api_access_request/?user__username={user.username}',
            body=json.dumps(data),
            content_type='application/json',
            status=status
        )

    def mock_api_access_request_with_configurable_results(self, lms_url, user, status=200, results=None):
        """
        Mock the api access requests endpoint response of the LMS.
        """
        data = {
            'count': len(results),
            'num_pages': 1,
            'current_page': 1,
            'results': results,
            'next': None,
            'start': 0,
            'previous': None
        }

        responses.add(
            responses.GET,
            lms_url.rstrip('/') + f'/api-admin/api/v1/api_access_request/?user__username={user.username}',
            body=json.dumps(data),
            content_type='application/json',
            status=status
        )

    def mock_api_access_request_with_invalid_data(self, lms_url, user, status=200, response_overrides=None):
        """
        Mock the api access requests endpoint response of the LMS.
        """
        data = response_overrides or {}

        responses.add(
            responses.GET,
            lms_url.rstrip('/') + f'/api-admin/api/v1/api_access_request/?user__username={user.username}',
            body=json.dumps(data),
            content_type='application/json',
            status=status
        )
