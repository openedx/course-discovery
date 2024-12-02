from urllib.parse import urlencode

import ddt
from django.test import Client, TestCase
from pytest import mark
from rest_framework import status

from course_discovery.apps.core.tests.factories import UserFactory
from course_discovery.apps.course_metadata.tests.factories import (
    CourseFactory, CourseRunFactory, RestrictedCourseRunFactory
)
from course_discovery.apps.learner_pathway.choices import PathwayStatus
from course_discovery.apps.learner_pathway.tests.factories import (
    LearnerPathwayCourseFactory, LearnerPathwayFactory, LearnerPathwayProgramFactory, LearnerPathwayStepFactory
)

USER_PASSWORD = 'QWERTY'
LEARNER_PATHWAY_DATA = {
    'uuid': '6b8742ce-f294-4674-aacb-34fbf75249de',
    'title': 'journey to comics',
    'status': PathwayStatus.Active.value,
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
                    'content_type': 'program',
                    'courses': [
                        {
                            'key': 'BB+BB102',
                            'course_runs': [
                                {
                                    'key': 'course-v1:BB+BB102+1T2024',
                                }
                            ]
                        }
                    ],
                }
            ]
        }
    ]
}
LEARNER_PATHWAY_UUID = LEARNER_PATHWAY_DATA['uuid']
LEARNER_PATHWAY_COURSE_KEY = LEARNER_PATHWAY_DATA['steps'][0]['courses'][0]['key']
LEARNER_PATHWAY_COURSE_RUN_KEY = LEARNER_PATHWAY_DATA['steps'][0]['courses'][0]['course_runs'][0]['key']
LEARNER_PATHWAY_PROGRAM_UUID = LEARNER_PATHWAY_DATA['steps'][0]['programs'][0]['uuid']


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
        self.learner_pathway_course__course_run = CourseRunFactory(
            course=self.learner_pathway_course.course,
            key=LEARNER_PATHWAY_DATA['steps'][0]['courses'][0]['course_runs'][0]['key'],
            status='published',
        )
        self.learner_pathway_program_course = CourseFactory(
            key=LEARNER_PATHWAY_DATA['steps'][0]['programs'][0]['courses'][0]['key']
        )
        LearnerPathwayProgramFactory(
            step=learner_pathway_step,
            program__uuid=LEARNER_PATHWAY_DATA['steps'][0]['programs'][0]['uuid'],
            program__title=LEARNER_PATHWAY_DATA['steps'][0]['programs'][0]['title'],
            program__subtitle=LEARNER_PATHWAY_DATA['steps'][0]['programs'][0]['short_description'],
            program__courses=[self.learner_pathway_program_course],
        )
        CourseRunFactory(
            course=self.learner_pathway_program_course,
            key=LEARNER_PATHWAY_DATA['steps'][0]['programs'][0]['courses'][0]['course_runs'][0]['key'],
            status='published',
        )

        self.client.login(username=self.user.username, password=USER_PASSWORD)

        self.view_url = '/api/v1/learner-pathway/{}/'.format(self.learner_pathway.uuid)  # reverse('learner-pathway')

    def _verify_learner_pathway_data(self, api_response, expected_data):
        """
        Verify that learner pathway api response matches the expected data.
        """
        if not isinstance(api_response, dict):
            data = api_response.json()
        else:
            data = api_response

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
            status=PathwayStatus.Active.value,
            overview='Test overview for Test Pathway 2',
        )
        url = f'/api/v1/learner-pathway/?uuid={self.learner_pathway.uuid},{another_learner_pathway.uuid}'
        api_response = self.client.get(url)
        data = api_response.json()
        assert data['count'] == 2
        assert data['results'][0]['uuid'] == self.learner_pathway.uuid
        assert data['results'][1]['uuid'] == another_learner_pathway.uuid

    @ddt.data([True, 2], [False, 1])
    @ddt.unpack
    def test_learner_pathway_restricted_runs(self, add_restriction_param, expected_run_count):
        restricted_run = CourseRunFactory(
            course=self.learner_pathway_course.course,
            key='course-v1:AA+AA101+3T2024',
            status='published',
        )
        RestrictedCourseRunFactory(course_run=restricted_run, restriction_type='custom-b2c')
        url = '/api/v1/learner-pathway/'
        if add_restriction_param:
            url += '?include_restricted=custom-b2c'

        api_response = self.client.get(url)
        data = api_response.json()
        assert len(data['results'][0]['steps'][0]['courses'][0]['course_runs']) == expected_run_count

    def test_learner_pathway_api_returns_active_pathway_only(self):
        """
        Verify that learner pathway api returns active pathway only.
        """
        self.learner_pathway.status = PathwayStatus.Inactive.value
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
        self._verify_learner_pathway_data(data, LEARNER_PATHWAY_DATA)

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


@ddt.ddt
class TestLearnerPathwayStepViewSet(TestCase):
    """
    Tests for LearnerPathwayStepViewSet.
    """
    def setUp(self):
        super().setUp()
        self.user = UserFactory.create(is_staff=True, is_active=True)
        self.user.set_password(USER_PASSWORD)
        self.user.save()
        self.client = Client()

        self.learner_pathway = LearnerPathwayFactory(
            uuid=LEARNER_PATHWAY_DATA['uuid'],
            title=LEARNER_PATHWAY_DATA['title'],
            status=LEARNER_PATHWAY_DATA['status'],
            overview=LEARNER_PATHWAY_DATA['overview'],
        )
        self.learner_pathway_step = LearnerPathwayStepFactory(
            pathway=self.learner_pathway,
            uuid=LEARNER_PATHWAY_DATA['steps'][0]['uuid'],
            min_requirement=LEARNER_PATHWAY_DATA['steps'][0]['min_requirement'],
        )
        self.learner_pathway_course = LearnerPathwayCourseFactory(
            step=self.learner_pathway_step,
            course__key=LEARNER_PATHWAY_DATA['steps'][0]['courses'][0]['key'],
            course__title=LEARNER_PATHWAY_DATA['steps'][0]['courses'][0]['title'],
            course__short_description=LEARNER_PATHWAY_DATA['steps'][0]['courses'][0]['short_description'],
        )
        self.learner_pathway_course_run = CourseRunFactory(
            course=self.learner_pathway_course.course,
            key=LEARNER_PATHWAY_DATA['steps'][0]['courses'][0]['course_runs'][0]['key'],
            status='published',
        )
        self.learner_pathway_program_course = CourseFactory(
            key=LEARNER_PATHWAY_DATA['steps'][0]['programs'][0]['courses'][0]['key']
        )
        LearnerPathwayProgramFactory(
            step=self.learner_pathway_step,
            program__uuid=LEARNER_PATHWAY_DATA['steps'][0]['programs'][0]['uuid'],
            program__title=LEARNER_PATHWAY_DATA['steps'][0]['programs'][0]['title'],
            program__subtitle=LEARNER_PATHWAY_DATA['steps'][0]['programs'][0]['short_description'],
            program__courses=[self.learner_pathway_program_course],
        )
        CourseRunFactory(
            course=self.learner_pathway_program_course,
            key=LEARNER_PATHWAY_DATA['steps'][0]['programs'][0]['courses'][0]['course_runs'][0]['key'],
            status='published',
        )

        self.client.login(username=self.user.username, password=USER_PASSWORD)

        self.view_url = f'/api/v1/learner-pathway-step/{self.learner_pathway_step.uuid}/'

    def _verify_learner_pathway_step_data(self, api_response, expected_data):
        """
        Verify that learner pathway step api response matches the expected data.
        """
        data = api_response.json()

        # Verify learner pathway step data
        assert data['uuid'] == expected_data['uuid']
        assert data['min_requirement'] == expected_data['min_requirement']

        # Verify associated course data
        api_response_course = data['courses'][0]
        expected_course_data = expected_data['courses'][0]
        for key, value in expected_course_data.items():
            assert api_response_course[key] == value

        # Verify course run data (published course runs)
        assert api_response_course['course_runs'][0]['key'] == expected_course_data['course_runs'][0]['key']

        # Verify program data
        api_response_program = data['programs'][0]
        expected_program_data = expected_data['programs'][0]
        for key, value in expected_program_data.items():
            assert api_response_program[key] == value

    def test_learner_pathway_step_api(self):
        """
        Verify that learner pathway step api returns the expected response.
        """
        api_response = self.client.get(self.view_url)
        self._verify_learner_pathway_step_data(api_response, LEARNER_PATHWAY_DATA['steps'][0])

    @ddt.data([True, 2], [False, 1])
    @ddt.unpack
    def test_learner_pathway_step_restricted_runs(self, add_restriction_param, expected_run_count):
        """
        Verify that restricted course runs are handled correctly based on query parameters.
        """
        restricted_run = CourseRunFactory(
            course=self.learner_pathway_course.course,
            key='course-v1:AA+AA101+3T2024',
            status='published',
        )
        RestrictedCourseRunFactory(course_run=restricted_run, restriction_type='custom-b2c')

        url = f'/api/v1/learner-pathway-step/{self.learner_pathway_step.uuid}/'
        if add_restriction_param:
            url += '?include_restricted=custom-b2c'

        api_response = self.client.get(url)
        data = api_response.json()
        assert len(data['courses'][0]['course_runs']) == expected_run_count


@ddt.ddt
class TestLearnerPathwayCourseViewSet(TestCase):
    """
    Tests for LearnerPathwayCourseViewSet.
    """
    def setUp(self):
        super().setUp()
        self.user = UserFactory.create(is_staff=True, is_active=True)
        self.user.set_password(USER_PASSWORD)
        self.user.save()
        self.client = Client()

        self.learner_pathway = LearnerPathwayFactory(
            uuid=LEARNER_PATHWAY_DATA['uuid'],
            title=LEARNER_PATHWAY_DATA['title'],
            status=LEARNER_PATHWAY_DATA['status'],
            overview=LEARNER_PATHWAY_DATA['overview'],
        )
        self.learner_pathway_step = LearnerPathwayStepFactory(
            pathway=self.learner_pathway,
            uuid=LEARNER_PATHWAY_DATA['steps'][0]['uuid'],
            min_requirement=LEARNER_PATHWAY_DATA['steps'][0]['min_requirement'],
        )
        self.learner_pathway_course = LearnerPathwayCourseFactory(
            step=self.learner_pathway_step,
            course__key=LEARNER_PATHWAY_DATA['steps'][0]['courses'][0]['key'],
            course__title=LEARNER_PATHWAY_DATA['steps'][0]['courses'][0]['title'],
            course__short_description=LEARNER_PATHWAY_DATA['steps'][0]['courses'][0]['short_description'],
        )
        self.learner_pathway_course_run = CourseRunFactory(
            course=self.learner_pathway_course.course,
            key=LEARNER_PATHWAY_DATA['steps'][0]['courses'][0]['course_runs'][0]['key'],
            status='published',
        )

        self.client.login(username=self.user.username, password=USER_PASSWORD)

        self.view_url = f'/api/v1/learner-pathway-course/{self.learner_pathway_course.uuid}/'

    def _verify_learner_pathway_course_data(self, api_response, expected_data):
        """
        Verify that learner pathway course api response matches the expected data.
        """
        data = api_response.json()

        # Verify course data
        assert data['key'] == expected_data['key']
        assert data['title'] == expected_data['title']
        assert data['short_description'] == expected_data['short_description']

        # Verify course run data (published course runs)
        api_response_course_run = data['course_runs'][0]
        assert api_response_course_run['key'] == expected_data['course_runs'][0]['key']

    def test_learner_pathway_course_api(self):
        """
        Verify that learner pathway course api returns the expected response.
        """
        api_response = self.client.get(self.view_url)
        self._verify_learner_pathway_course_data(api_response, LEARNER_PATHWAY_DATA['steps'][0]['courses'][0])

    @ddt.data([True, 2], [False, 1])
    @ddt.unpack
    def test_learner_pathway_course_restricted_runs(self, add_restriction_param, expected_run_count):
        """
        Verify that restricted course runs are handled correctly based on query parameters.
        """
        restricted_run = CourseRunFactory(
            course=self.learner_pathway_course.course,
            key='course-v1:AA+AA101+3T2024',
            status='published',
        )
        RestrictedCourseRunFactory(course_run=restricted_run, restriction_type='custom-b2c')

        url = f'/api/v1/learner-pathway-course/{self.learner_pathway_course.uuid}/'
        if add_restriction_param:
            url += '?include_restricted=custom-b2c'

        api_response = self.client.get(url)
        data = api_response.json()
        assert len(data['course_runs']) == expected_run_count


@ddt.ddt
class TestLearnerPathwayProgramViewSet(TransactionTestCase):
    """
    Tests for LearnerPathwayProgramViewSet.
    """
    serialized_rollback = True
    def setUp(self):
        super().setUp()
        self.user = UserFactory.create(is_staff=True, is_active=True)
        self.user.set_password(USER_PASSWORD)
        self.user.save()
        self.client = Client()

        self.learner_pathway = LearnerPathwayFactory(
            uuid=LEARNER_PATHWAY_DATA['uuid'],
            title=LEARNER_PATHWAY_DATA['title'],
            status=LEARNER_PATHWAY_DATA['status'],
            overview=LEARNER_PATHWAY_DATA['overview'],
        )
        self.learner_pathway_step = LearnerPathwayStepFactory(
            pathway=self.learner_pathway,
            uuid=LEARNER_PATHWAY_DATA['steps'][0]['uuid'],
            min_requirement=LEARNER_PATHWAY_DATA['steps'][0]['min_requirement'],
        )
        self.learner_pathway_program_course = CourseFactory(
            key=LEARNER_PATHWAY_DATA['steps'][0]['programs'][0]['courses'][0]['key']
        )
        self.learner_pathway_program = LearnerPathwayProgramFactory(
            step=self.learner_pathway_step,
            program__uuid=LEARNER_PATHWAY_DATA['steps'][0]['programs'][0]['uuid'],
            program__title=LEARNER_PATHWAY_DATA['steps'][0]['programs'][0]['title'],
            program__subtitle=LEARNER_PATHWAY_DATA['steps'][0]['programs'][0]['short_description'],
            program__courses=[self.learner_pathway_program_course]
        )
        CourseRunFactory(
            course=self.learner_pathway_program_course,
            key=LEARNER_PATHWAY_DATA['steps'][0]['programs'][0]['courses'][0]['course_runs'][0]['key'],
            status='published',
        )

        self.client.login(username=self.user.username, password=USER_PASSWORD)

        self.view_url = f'/api/v1/learner-pathway-program/{self.learner_pathway_program.uuid}/'

    def _verify_learner_pathway_program_data(self, api_response, expected_data):
        """
        Verify that learner pathway program api response matches the expected data.
        """
        data = api_response.json()
        # Verify program data
        assert data['uuid'] == expected_data['uuid']
        assert data['title'] == expected_data['title']
        assert data['short_description'] == expected_data['short_description']

        # Verify course run data (published course runs)
        api_response_course_run = data['courses'][0]['course_runs'][0]
        assert api_response_course_run['key'] == expected_data['courses'][0]['course_runs'][0]['key']

    def test_learner_pathway_program_api(self):
        """
        Verify that learner pathway program api returns the expected response.
        """
        api_response = self.client.get(self.view_url)
        self._verify_learner_pathway_program_data(api_response, LEARNER_PATHWAY_DATA['steps'][0]['programs'][0])

    @ddt.data([True, 2], [False, 1])
    @ddt.unpack
    def test_learner_pathway_program_restricted_runs(self, add_restriction_param, expected_run_count):
        """
        Verify that restricted program course runs are handled correctly based on query parameters.
        """
        restricted_run = CourseRunFactory(
            course=self.learner_pathway_program.program.courses.first(),
            key='course-v1:AA+AA101+3T2024',
            status='published',
        )
        RestrictedCourseRunFactory(course_run=restricted_run, restriction_type='custom-b2c')

        url = f'/api/v1/learner-pathway-program/{self.learner_pathway_program.uuid}/'
        if add_restriction_param:
            url += '?include_restricted=custom-b2c'

        api_response = self.client.get(url)
        data = api_response.json()
        assert len(data['courses'][0]['course_runs']) == expected_run_count
