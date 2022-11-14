import json
import logging

import pytest
import responses
from django.conf import settings
from django_elasticsearch_dsl.registries import registry
from elasticsearch_dsl.connections import get_connection

from course_discovery.apps.core.utils import ElasticsearchUtils

logger = logging.getLogger(__name__)


@pytest.mark.usefixtures('elasticsearch_dsl_default_connection')
class ElasticsearchTestMixin:
    def setUp(self):
        super().setUp()
        self.es = get_connection()

    def refresh_index(self):
        """
        Refreshes an index.

        https://www.elastic.co/guide/en/elasticsearch/reference/current/indices-refresh.html
        """
        for index in registry.get_indices():
            ElasticsearchUtils.refresh_index(self.es, index._name)  # pylint: disable=protected-access

    def reindex_course_runs(self, course):
        for course_run in course.course_runs.all():
            registry.update(course_run)

    def reindex_courses(self, program):
        for course in program.courses.all():
            registry.update(course)
            self.reindex_course_runs(course)

    def reindex_people(self, person):
        registry.update(person)


class LMSAPIClientMixin:
    def mock_access_token(self):
        responses.add(
            responses.POST,
            settings.BACKEND_SERVICE_EDX_OAUTH2_PROVIDER_URL + '/access_token',
            body=json.dumps({'access_token': 'abcd', 'expires_in': 60}),
            status=200,
        )

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
            'previous': None,
        }

        responses.add(
            responses.GET,
            lms_url.rstrip('/') + f'/api-admin/api/v1/api_access_request/?user__username={user.username}',
            body=json.dumps(data),
            content_type='application/json',
            status=status,
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
            'previous': None,
        }

        responses.add(
            responses.GET,
            lms_url.rstrip('/') + f'/api-admin/api/v1/api_access_request/?user__username={user.username}',
            body=json.dumps(data),
            content_type='application/json',
            status=status,
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
            status=status,
        )

    def mock_blocks_data_request(self, lms_url, override_blocks=None, status=200):
        """
        Mock the blocks data requests endpoint response of the LMS.
        """
        data = {
            'root': 'block-v1:edX+DemoX+Demo_Course+type@course+block@course',
            'blocks': {
                'block-v1:edX+DemoX+Demo_Course+type@html+block@030e35c4756a4ddc8d40b95fbbfff4d4': {
                    'id': 'block-v1:edX+DemoX+Demo_Course+type@html+block@030e35c4756a4ddc8d40b95fbbfff4d4',
                    'block_id': '030e35c4756a4ddc8d40b95fbbfff4d4',
                    'type': 'html',
                    'display_name': 'Blank HTML Page',
                },
                'block-v1:edX+DemoX+Demo_Course+type@video+block@0b9e39477cf34507a7a48f74be381fdd': {
                    'id': 'block-v1:edX+DemoX+Demo_Course+type@video+block@0b9e39477cf34507a7a48f74be381fdd',
                    'block_id': '0b9e39477cf34507a7a48f74be381fdd',
                    'type': 'video',
                    'display_name': 'Welcome!',
                },
                'block-v1:edX+DemoX+Demo_Course+type@vertical+block@vertical_0270f6de40fc': {
                    'id': 'block-v1:edX+DemoX+Demo_Course+type@vertical+block@vertical_0270f6de40fc',
                    'block_id': 'vertical_0270f6de40fc',
                    'type': 'vertical',
                    'display_name': 'Introduction: Video and Sequences',
                    'children': [
                        'block-v1:edX+DemoX+Demo_Course+type@html+block@030e35c4756a4ddc8d40b95fbbfff4d4',
                        'block-v1:edX+DemoX+Demo_Course+type@video+block@0b9e39477cf34507a7a48f74be381fdd'
                    ]
                },
            }
        }
        if override_blocks is not None:
            data['blocks'] = override_blocks

        responses.add(
            responses.GET,
            lms_url,
            body=json.dumps(data),
            content_type='application/json',
            status=status,
        )
        return data

    def mock_block_metadata_request(self, base_url, status=200):
        data = {
            'block-v1:edX+DemoX+Demo_Course+type@html+block@030e35c4756a4ddc8d40b95fbbfff4d4': {
                'id': 'block-v1:edX+DemoX+Demo_Course+type@html+block@030e35c4756a4ddc8d40b95fbbfff4d4',
                'type': 'html',
                'index_dictionary': {
                    'content': {
                        'display_name': 'Blank HTML Page',
                        'html_content': 'Welcome to the Open edX Demo Course Introduction.'
                    },
                    'content_type': 'Text'
                }
            },
            'block-v1:edX+DemoX+Demo_Course+type@video+block@0b9e39477cf34507a7a48f74be381fdd': {
                'id': 'block-v1:edX+DemoX+Demo_Course+type@video+block@0b9e39477cf34507a7a48f74be381fdd',
                'type': 'video',
                'index_dictionary': {
                    'content': {
                        'display_name': 'Welcome!',
                        'transcript_en': ' ERIC: Hi, and welcome to the edX demonstration course.'
                    },
                    'content_type': 'Video'
                }
            },
            'block-v1:edX+DemoX+Demo_Course+type@vertical+block@vertical_0270f6de40fc': {
                'id': 'block-v1:edX+DemoX+Demo_Course+type@vertical+block@vertical_0270f6de40fc',
                'type': 'vertical',
                'index_dictionary': {
                    'content': {
                        'display_name': 'Introduction: Video and Sequences'
                    },
                    'content_type': 'Sequence'
                },
            }
        }
        for block_id, block_body in data.items():
            responses.add(
                responses.GET,
                base_url + block_id,
                body=json.dumps(block_body),
                content_type='application/json',
                status=status,
            )
        return data
