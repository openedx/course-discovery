""" Test cases for api/v2/search/all """

import json

import ddt
from django.urls import reverse

from course_discovery.apps.api.v1.tests.test_views import mixins
from course_discovery.apps.core.tests.mixins import ElasticsearchTestMixin
from course_discovery.apps.course_metadata.choices import CourseRunStatus
from course_discovery.apps.course_metadata.tests.factories import CourseFactory, CourseRunFactory, PersonFactory
from course_discovery.apps.learner_pathway.models import LearnerPathway
from course_discovery.apps.learner_pathway.tests.factories import LearnerPathwayStepFactory


@ddt.ddt
class AggregateSearchViewSetV2Tests(mixins.LoginMixin, ElasticsearchTestMixin, mixins.APITestCase):
    list_path = reverse("api:v2:search-all-list")

    def fetch_page_data(self, page_size, search_after=None):
        query_params = {"page_size": page_size}
        if search_after:
            query_params["search_after"] = search_after
        response = self.client.get(self.list_path, data=query_params)
        assert response.status_code == 200
        return response.json()

    def validate_page_data(self, page_data, expected_size):
        assert all("sort" in obj for obj in page_data["results"]), "Not all objects have a 'sort' field"
        assert all(
            "aggregation_uuid" in obj for obj in page_data["results"]
        ), "Not all objects have an 'aggregation_uuid' field"
        assert (
            len(page_data["results"]) == expected_size
        ), f"Page does not have the expected number of results ({expected_size})"

    def test_results_include_aggregation_uuid_and_sort_fields(self):
        """
        Test that search results include 'aggregation_uuid' and 'sort' fields
        and that the total result count matches the expected value.
        """
        PersonFactory.create_batch(5, partner=self.partner)
        courses = CourseFactory.create_batch(5, partner=self.partner)

        for course in courses:
            CourseRunFactory(
                course__partner=self.partner,
                course=course,
                type__is_marketable=True,
                status=CourseRunStatus.Published,
            )
        response = self.client.get(self.list_path)
        response_data = response.json()
        assert response.status_code == 200
        assert response_data["count"] == 15
        self.validate_page_data(response_data, 15)

    @ddt.data((True, 10), (False, 0))
    @ddt.unpack
    def test_learner_pathway_feature_flag(self, include_learner_pathways, expected_result_count):
        """
        Test the inclusion of learner pathways in search results based on a feature flag.
        """
        LearnerPathwayStepFactory.create_batch(10, pathway__partner=self.partner)
        pathways = LearnerPathway.objects.all()
        assert pathways.count() == 10
        query = {
            "include_learner_pathways": include_learner_pathways,
        }

        response = self.client.get(self.list_path, data=query)
        assert response.status_code == 200
        response_data = response.json()

        assert response_data["count"] == expected_result_count

    def test_search_after_pagination(self):
        """
        Test paginated fetching of search results using 'search_after' param.
        """
        PersonFactory.create_batch(25, partner=self.partner)
        courses = CourseFactory.create_batch(25, partner=self.partner)

        for course in courses:
            CourseRunFactory(
                course__partner=self.partner,
                course=course,
                type__is_marketable=True,
                status=CourseRunStatus.Published,
            )

        page_size = 10
        response_data = self.fetch_page_data(page_size)

        assert response_data["count"] == 75  # Total objects: 25 Persons + 25 Courses + 25 CourseRuns
        self.validate_page_data(response_data, page_size)

        all_results = response_data["results"]
        next_token = response_data.get("next")

        while next_token:
            response_data = self.fetch_page_data(page_size, search_after=json.dumps(next_token))

            expected_size = min(page_size, 75 - len(all_results))
            self.validate_page_data(response_data, expected_size)

            all_results.extend(response_data["results"])
            next_token = response_data.get("next")

            if next_token:
                last_sort_value = response_data["results"][-1]["sort"]
                assert last_sort_value == next_token

        assert len(all_results) == 75, "The total number of results does not match the expected count"

        single_page_response = self.client.get(self.list_path, data={"page_size": 75})
        assert single_page_response.status_code == 200
        single_page_data = single_page_response.json()

        assert (
            len(single_page_data["results"]) == 75
        ), "The total number of results in the single request does not match the expected count"
        assert (
            single_page_data["results"] == all_results
        ), "Combined pagination results do not match single request results"
