from urllib.parse import urlencode

import ddt
from django.test import Client, TestCase
from django.urls import reverse
from pytest import mark
from rest_framework import status

from course_discovery.apps import learner_pathway
from course_discovery.apps.core.tests.factories import UserFactory
from course_discovery.apps.course_metadata.tests.factories import CourseRunFactory
from course_discovery.apps.learner_pathway.choices import PathwayStatus
from course_discovery.apps.learner_pathway.tests.factories import (
    LearnerPathwayCourseFactory, LearnerPathwayFactory, LearnerPathwayProgramFactory, LearnerPathwayStepFactory
)

USER_PASSWORD = 'QWERTY'
LEARNER_PATHWAY_DATA = {
    'uuid': '6b8742ce-f294-4674-aacb-34fbf75249de',
    'title': 'journey to comics',
    'status': PathwayStatus.Active,
    'banner_image': '',
    'card_image': '',
    'overview': 'learn all about Marvel and DC',
    'steps': [
        {
            'uuid': '9d91b42a-f3e4-461a-b9e1-e53a4fc927ed',
            'min_requirement': 2,
            'courses': [
                {
                    'key': 'AA+AA101',
                    'title': 'intro to basics',
                    'short_description': 'comic basics',
                    'content_type': 'course',
                    'course_runs': [
                        {
                            'key': 'course-v1:AA+AA101+1T2022',
                        }
                    ]
                }
            ],
            'programs': [
                {
                    'uuid': '1f301a72-f344-4a31-9e9a-e0b04d8d86b2',
                    'title': 'test-program-0',
                    'short_description': 'into to more basics',
                    'content_type': 'program'
                }
            ]
        }
    ]
}
LEARNER_PATHWAY_UUID = LEARNER_PATHWAY_DATA['uuid']
LEARNER_PATHWAY_COURSE_KEY = LEARNER_PATHWAY_DATA['steps'][0]['courses'][0]['key']
LEARNER_PATHWAY_COURSE_RUN_KEY = LEARNER_PATHWAY_DATA['steps'][0]['courses'][0]['course_runs'][0]['key']
LEARNER_PATHWAY_PROGRAM_UUID = LEARNER_PATHWAY_DATA['steps'][0]['programs'][0]['uuid']

LEARNER_PATHWAY_SNAPSHOT_DATA = {
    "uuid": "6b8742ce-f294-4674-aacb-34fbf75249de",
    "status": "active",
    "steps": [
        {
            "uuid": "9d91b42a-f3e4-461a-b9e1-e53a4fc927ed",
            "min_requirement": 2,
            "courses": [
                {
                    "key": "AA+AA101",
                    "course_runs": [
                        {
                            "key": "course-v1:AA+AA101+1T2022"
                        }
                    ]
                }
            ],
            "programs": [
                {
                    "uuid": "1f301a72-f344-4a31-9e9a-e0b04d8d86b2"
                }
            ]
        }
    ]
}


@mark.django_db
@ddt.ddt
class TestLearnerPathwayViewSet(TestCase):
    """
    Tests for LearnerPathwayViewSet.
    """
    def setUp(self):
        """
        Test set up
        """
        super().setUp()
        self.user = UserFactory.create(is_staff=True, is_active=True)
        self.user.set_password(USER_PASSWORD)
        self.user.save()
        self.client = Client()

        # create learner pathway data
        self.learner_pathway = LearnerPathwayFactory(
            uuid=LEARNER_PATHWAY_DATA['uuid'],
            title=LEARNER_PATHWAY_DATA['title'],
            status=LEARNER_PATHWAY_DATA['status'],
            overview=LEARNER_PATHWAY_DATA['overview'],
        )
        learner_pathway_step = LearnerPathwayStepFactory(
            pathway=self.learner_pathway,
            uuid=LEARNER_PATHWAY_DATA['steps'][0]['uuid'],
            min_requirement=LEARNER_PATHWAY_DATA['steps'][0]['min_requirement'],
        )
        self.learner_pathway_course = LearnerPathwayCourseFactory(
            step=learner_pathway_step,
            course__key=LEARNER_PATHWAY_DATA['steps'][0]['courses'][0]['key'],
            course__title=LEARNER_PATHWAY_DATA['steps'][0]['courses'][0]['title'],
            course__short_description=LEARNER_PATHWAY_DATA['steps'][0]['courses'][0]['short_description'],
        )
        __ = CourseRunFactory(
            course=self.learner_pathway_course.course,
            key=LEARNER_PATHWAY_DATA['steps'][0]['courses'][0]['course_runs'][0]['key'],
            status='published',
        )
        LearnerPathwayProgramFactory(
            step=learner_pathway_step,
            program__uuid=LEARNER_PATHWAY_DATA['steps'][0]['programs'][0]['uuid'],
            program__title=LEARNER_PATHWAY_DATA['steps'][0]['programs'][0]['title'],
            program__subtitle=LEARNER_PATHWAY_DATA['steps'][0]['programs'][0]['short_description'],
        )

        self.client.login(username=self.user.username, password=USER_PASSWORD)

        self.view_url = '/api/v1/learner-pathway/{}/'.format(self.learner_pathway.uuid)  # reverse('learner-pathway')

    def _verify_learner_pathway_data(self, api_response, expected_data):
        """
        Verify that learner pathway api response matches the expected data.
        """
        data = api_response.json()

        # verify pathway data
        assert data['uuid'] == expected_data['uuid']
        assert data['title'] == expected_data['title']
        assert data['status'] == expected_data['status']
        assert data['overview'] == expected_data['overview']
        # banner image and card image should not be empty
        assert data['banner_image']
        assert data['card_image']

        # verify step data
        assert data['steps'][0]['min_requirement'] == expected_data['steps'][0]['min_requirement']
        assert data['steps'][0]['uuid'] == expected_data['steps'][0]['uuid']

        # verify step course data
        api_response_step_course = data['steps'][0]['courses'][0]
        expected_lerner_pathway_step_course = expected_data['steps'][0]['courses'][0]
        for key, value in expected_lerner_pathway_step_course.items():
            assert api_response_step_course[key] == value

        # course card_image_url should not be empty
        assert api_response_step_course['card_image_url']

        # verify step program data
        api_response_step_program = data['steps'][0]['programs'][0]
        expected_lerner_pathway_step_program = expected_data['steps'][0]['programs'][0]
        for key, value in expected_lerner_pathway_step_program.items():
            assert api_response_step_program[key] == value

        # program card_image_url should not be empty
        assert api_response_step_course['card_image_url']

    def test_learner_pathway_api(self):
        """
        Verify that learner pathway api returns the expected response.
        """
        api_response = self.client.get(self.view_url)
        self._verify_learner_pathway_data(api_response, LEARNER_PATHWAY_DATA)

    def test_learner_pathway_api_filtering(self):
        """
        Verify that comma-delimited filtering on pathway uuids is enabled for learner pathway api .
        """
        another_learner_pathway = LearnerPathwayFactory(
            uuid='aaa7c03d-d2cf-420c-b109-aa227f770655',
            title='Test Pathway 2',
            status=PathwayStatus.Active,
            overview='Test overview for Test Pathway 2',
        )
        url = f'/api/v1/learner-pathway/?uuid={self.learner_pathway.uuid},{another_learner_pathway.uuid}'
        api_response = self.client.get(url)
        data = api_response.json()
        assert data['count'] == 2
        assert data['results'][0]['uuid'] == self.learner_pathway.uuid
        assert data['results'][1]['uuid'] == another_learner_pathway.uuid

    def test_learner_pathway_api_returns_active_pathway_only(self):
        """
        Verify that learner pathway api returns active pathway only.
        """
        self.learner_pathway.status = PathwayStatus.Inactive
        self.learner_pathway.save()

        api_response = self.client.get(self.view_url)
        assert api_response.status_code == status.HTTP_404_NOT_FOUND

    def test_learner_pathway_snapshot_api(self):
        """
        Verify that learner pathway snapshot api  returns the expected response.
        """
        snapshot_url = f'{self.view_url}snapshot/'
        api_response = self.client.get(snapshot_url)
        data = api_response.json()
        # remove id/pk of the object, we don't need to compare it
        data.pop('id')
        assert data == LEARNER_PATHWAY_SNAPSHOT_DATA

    @ddt.data(
        {
            'query_params': {},
            'response': [],
        },
        {
            'query_params': {
                'course_keys': LEARNER_PATHWAY_COURSE_KEY,
            },
            'response': [LEARNER_PATHWAY_UUID],
        },
        {
            'query_params': {
                'course_keys': LEARNER_PATHWAY_COURSE_RUN_KEY,
            },
            'response': [LEARNER_PATHWAY_UUID],
        },
        {
            'query_params': {
                'program_uuids': LEARNER_PATHWAY_PROGRAM_UUID,
            },
            'response': [LEARNER_PATHWAY_UUID],
        },
        {
            'query_params': {
                'course_keys': LEARNER_PATHWAY_COURSE_KEY,
                'program_uuids': LEARNER_PATHWAY_PROGRAM_UUID,
            },
            'response': [LEARNER_PATHWAY_UUID],
        },
    )
    @ddt.unpack
    def test_learner_pathway_uuids_endpoint(self, query_params, response):
        """
        Verify that learner pathway uuids endpoint returns the correct uuids.
        """
        learner_pathway_uuids_url = f'/api/v1/learner-pathway/uuids/?{urlencode(query_params)}'
        api_response = self.client.get(learner_pathway_uuids_url)
        assert api_response.json() == response
