import math

import ddt
import pytest
import responses
from django.urls import reverse

from course_discovery.apps.api.v1.tests.test_views.mixins import APITestCase, OAuth2Mixin
from course_discovery.apps.core.tests.factories import USER_PASSWORD, UserFactory
from course_discovery.apps.course_metadata.tests.factories import CourseFactory, OrganizationFactory
from course_discovery.apps.taxonomy_support.api.v1.tests.factories import CourseRecommendationFactory


@ddt.ddt
@pytest.mark.usefixtures('django_cache')
class CourseViewSetTests(OAuth2Mixin, APITestCase):
    def setUp(self):
        super().setUp()
        self.user = UserFactory()
        self.request.user = self.user
        self.client.login(username=self.user.username, password=USER_PASSWORD)
        self.mock_access_token()

        self.org = OrganizationFactory(key='edX', partner=self.partner)
        self.diff_org = OrganizationFactory()
        self.course = CourseFactory(authoring_organizations=[self.org])

        self.path = reverse('taxonomy_support:course_recommendations', args=(self.course.key,))

    def tearDown(self):
        super().tearDown()
        self.client.logout()

    def create_course_recommendations(self, course, all_recommends_count, same_partner_recommends_count):
        """
        Creates Course recommendations and relative data.
        """
        diff_recommends_count = all_recommends_count - same_partner_recommends_count
        same_partner_recommended_courses = CourseFactory.create_batch(
            same_partner_recommends_count, authoring_organizations=[self.org]
        )
        diff_partner_recommended_courses = CourseFactory.create_batch(
            diff_recommends_count, authoring_organizations=[self.diff_org]
        )
        for recommended_course in same_partner_recommended_courses + diff_partner_recommended_courses:
            CourseRecommendationFactory(course=course, recommended_course=recommended_course)

    def assert_ordering(self, recommendations):
        """
        Asserts recommendations ordering as per expectation
        """
        last_skills_intersection_ratio = 1.0
        last_skills_intersection_length = math.inf
        for recommended_course in recommendations:
            current_intersection_ratio = recommended_course['skills_intersection_ratio']
            current_skills_intersection_length = recommended_course['skills_intersection_length']
            assert current_intersection_ratio < last_skills_intersection_ratio \
                   or (current_intersection_ratio == last_skills_intersection_ratio and
                       current_skills_intersection_length <= last_skills_intersection_length)
            last_skills_intersection_ratio = current_intersection_ratio
            last_skills_intersection_length = current_skills_intersection_length

    def assert_response(self, expected_all_recommends_count, expected_same_partner_recommends_count, expected_queries):
        """
        Assert recommendation response

        * tests number of queries
        * tests status code
        * tests data returned by the endpoint return correct count for same partner and different partner
        * test there ordering
        """
        with self.assertNumQueries(expected_queries):
            response = self.client.get(self.path)
            assert response.status_code == 200
            results = response.json()
            assert len(results['all_recommendations']) == expected_all_recommends_count
            assert len(results['same_partner_recommendations']) == expected_same_partner_recommends_count
            self.assert_ordering(results['all_recommendations'])
            self.assert_ordering(results['same_partner_recommendations'])

    @ddt.data(
        (50, 12, 8),
        (10, 7, 8),
        (3, 0, 8),
        (0, 0, 8)
    )
    @ddt.unpack
    @responses.activate
    def test_course_recommendations(
            self,
            all_recommends_count,
            same_partner_recommends_count,
            expected_queries
    ):
        """
        Test all possible positive scenarios.
        """
        self.create_course_recommendations(self.course, all_recommends_count, same_partner_recommends_count)
        self.assert_response(all_recommends_count, same_partner_recommends_count, expected_queries)

    @responses.activate
    def test_course_not_found(self):
        """Test status when course not found."""
        path = reverse('taxonomy_support:course_recommendations', args=('NO+COURSE',))
        response = self.client.get(path)
        assert response.status_code == 404
        assert response.json()['detail'] == 'Not found.'

    @responses.activate
    def test_unauthenticated_user(self):
        """
        Test accessing the endpoint without login.
        """
        self.client.logout()
        response = self.client.get(self.path)
        assert response.status_code == 401
