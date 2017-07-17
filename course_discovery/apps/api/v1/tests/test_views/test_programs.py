import urllib.parse

import ddt
from django.core.cache import cache
from django.urls import reverse
from rest_framework.test import APITestCase

from course_discovery.apps.api.serializers import MinimalProgramSerializer
from course_discovery.apps.api.v1.tests.test_views.mixins import SerializationMixin
from course_discovery.apps.api.v1.views.programs import ProgramViewSet
from course_discovery.apps.core.tests.factories import USER_PASSWORD, UserFactory
from course_discovery.apps.core.tests.helpers import make_image_file
from course_discovery.apps.course_metadata.choices import ProgramStatus
from course_discovery.apps.course_metadata.models import Program
from course_discovery.apps.course_metadata.tests.factories import (
    CorporateEndorsementFactory, CourseFactory, CourseRunFactory, EndorsementFactory, ExpectedLearningItemFactory,
    JobOutlookItemFactory, OrganizationFactory, PersonFactory, ProgramFactory, VideoFactory
)


@ddt.ddt
class ProgramViewSetTests(SerializationMixin, APITestCase):
    list_path = reverse('api:v1:program-list')

    def setUp(self):
        super(ProgramViewSetTests, self).setUp()
        self.user = UserFactory(is_staff=True, is_superuser=True)
        self.client.login(username=self.user.username, password=USER_PASSWORD)

        # Clear the cache between test cases, so they don't interfere with each other.
        cache.clear()

    def create_program(self):
        organizations = [OrganizationFactory()]
        person = PersonFactory()

        course = CourseFactory()
        CourseRunFactory(course=course, staff=[person])

        program = ProgramFactory(
            courses=[course],
            authoring_organizations=organizations,
            credit_backing_organizations=organizations,
            corporate_endorsements=CorporateEndorsementFactory.create_batch(1),
            individual_endorsements=EndorsementFactory.create_batch(1),
            expected_learning_items=ExpectedLearningItemFactory.create_batch(1),
            job_outlook_items=JobOutlookItemFactory.create_batch(1),
            banner_image=make_image_file('test_banner.jpg'),
            video=VideoFactory()
        )
        return program

    def assert_retrieve_success(self, program, querystring=None):
        """ Verify the retrieve endpoint succesfully returns a serialized program. """
        url = reverse('api:v1:program-detail', kwargs={'uuid': program.uuid})

        if querystring:
            url += '?' + urllib.parse.urlencode(querystring)

        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        return response

    def test_authentication(self):
        """ Verify the endpoint requires the user to be authenticated. """
        response = self.client.get(self.list_path)
        self.assertEqual(response.status_code, 200)

        self.client.logout()
        response = self.client.get(self.list_path)
        self.assertEqual(response.status_code, 403)

    def test_retrieve(self):
        """ Verify the endpoint returns the details for a single program. """
        program = self.create_program()
        with self.assertNumQueries(37):
            response = self.assert_retrieve_success(program)
        # property does not have the right values while being indexed
        del program._course_run_weeks_to_complete
        assert response.data == self.serialize_program(program)

        # Verify that repeated retrieve requests use the cache.
        with self.assertNumQueries(2):
            self.assert_retrieve_success(program)

        # Verify that requests including querystring parameters are cached separately.
        response = self.assert_retrieve_success(program, querystring={'use_full_course_serializer': 1})
        assert response.data == self.serialize_program(program, extra_context={'use_full_course_serializer': 1})

    @ddt.data(True, False)
    def test_retrieve_with_sorting_flag(self, order_courses_by_start_date):
        """ Verify the number of queries is the same with sorting flag set to true. """
        course_list = CourseFactory.create_batch(3)
        for course in course_list:
            CourseRunFactory(course=course)
        program = ProgramFactory(courses=course_list, order_courses_by_start_date=order_courses_by_start_date)
        # property does not have the right values while being indexed
        del program._course_run_weeks_to_complete
        with self.assertNumQueries(26):
            response = self.assert_retrieve_success(program)
        assert response.data == self.serialize_program(program)
        self.assertEqual(course_list, list(program.courses.all()))  # pylint: disable=no-member

    def test_retrieve_without_course_runs(self):
        """ Verify the endpoint returns data for a program even if the program's courses have no course runs. """
        course = CourseFactory()
        program = ProgramFactory(courses=[course])
        with self.assertNumQueries(20):
            response = self.assert_retrieve_success(program)
        assert response.data == self.serialize_program(program)

    def assert_list_results(self, url, expected, expected_query_count, extra_context=None):
        """
        Asserts the results serialized/returned at the URL matches those that are expected.
        Args:
            url (str): URL from which data should be retrieved
            expected (list[Program]): Expected programs

        Notes:
            The API usually returns items in reverse order of creation (e.g. newest first). You may need to reverse
            the values of `expected` if you encounter issues. This method will NOT do that reversal for you.

        Returns:
            None
        """
        with self.assertNumQueries(expected_query_count):
            response = self.client.get(url)

        self.assertEqual(
            response.data['results'],
            self.serialize_program(expected, many=True, extra_context=extra_context)
        )

    def test_list(self):
        """ Verify the endpoint returns a list of all programs. """
        expected = [self.create_program() for __ in range(3)]
        expected.reverse()
        self.assert_list_results(self.list_path, expected, 12)

        # Verify that repeated list requests use the cache.
        self.assert_list_results(self.list_path, expected, 2)

    def test_uuids_only(self):
        """
        Verify that the list view returns a simply list of UUIDs when the
        uuids_only query parameter is passed.
        """
        active = ProgramFactory.create_batch(3)
        retired = [ProgramFactory(status=ProgramStatus.Retired)]
        programs = active + retired

        querystring = {'uuids_only': 1}
        url = '{base}?{query}'.format(base=self.list_path, query=urllib.parse.urlencode(querystring))
        response = self.client.get(url)

        assert set(response.data) == {program.uuid for program in programs}

        # Verify that filtering (e.g., by status) is still supported.
        querystring['status'] = ProgramStatus.Retired
        url = '{base}?{query}'.format(base=self.list_path, query=urllib.parse.urlencode(querystring))
        response = self.client.get(url)

        assert set(response.data) == {program.uuid for program in retired}

    def test_filter_by_type(self):
        """ Verify that the endpoint filters programs to those of a given type. """
        program_type_name = 'foo'
        program = ProgramFactory(type__name=program_type_name)
        url = self.list_path + '?type=' + program_type_name
        self.assert_list_results(url, [program], 8)

        url = self.list_path + '?type=bar'
        self.assert_list_results(url, [], 3)

    def test_filter_by_types(self):
        """ Verify that the endpoint filters programs to those matching the provided ProgramType slugs. """
        expected = ProgramFactory.create_batch(2)
        expected.reverse()
        type_slugs = [p.type.slug for p in expected]
        url = self.list_path + '?types=' + ','.join(type_slugs)

        # Create a third program, which should be filtered out.
        ProgramFactory()

        self.assert_list_results(url, expected, 8)

    def test_filter_by_uuids(self):
        """ Verify that the endpoint filters programs to those matching the provided UUIDs. """
        expected = ProgramFactory.create_batch(2)
        expected.reverse()
        uuids = [str(p.uuid) for p in expected]
        url = self.list_path + '?uuids=' + ','.join(uuids)

        # Create a third program, which should be filtered out.
        ProgramFactory()

        self.assert_list_results(url, expected, 8)

    @ddt.data(
        (ProgramStatus.Unpublished, False, 3),
        (ProgramStatus.Active, True, 8),
    )
    @ddt.unpack
    def test_filter_by_marketable(self, status, is_marketable, expected_query_count):
        """ Verify the endpoint filters programs to those that are marketable. """
        url = self.list_path + '?marketable=1'
        ProgramFactory(marketing_slug='')
        programs = ProgramFactory.create_batch(3, status=status)
        programs.reverse()

        expected = programs if is_marketable else []
        self.assertEqual(list(Program.objects.marketable()), expected)
        self.assert_list_results(url, expected, expected_query_count)

    def test_filter_by_status(self):
        """ Verify the endpoint allows programs to filtered by one, or more, statuses. """
        active = ProgramFactory(status=ProgramStatus.Active)
        retired = ProgramFactory(status=ProgramStatus.Retired)

        url = self.list_path + '?status=active'
        self.assert_list_results(url, [active], 8)

        url = self.list_path + '?status=retired'
        self.assert_list_results(url, [retired], 8)

        url = self.list_path + '?status=active&status=retired'
        self.assert_list_results(url, [retired, active], 8)

    def test_filter_by_hidden(self):
        """ Endpoint should filter programs by their hidden attribute value. """
        hidden = ProgramFactory(hidden=True)
        not_hidden = ProgramFactory(hidden=False)

        url = self.list_path + '?hidden=True'
        self.assert_list_results(url, [hidden], 8)

        url = self.list_path + '?hidden=False'
        self.assert_list_results(url, [not_hidden], 8)

        url = self.list_path + '?hidden=1'
        self.assert_list_results(url, [hidden], 8)

        url = self.list_path + '?hidden=0'
        self.assert_list_results(url, [not_hidden], 8)

    def test_list_exclude_utm(self):
        """ Verify the endpoint returns marketing URLs without UTM parameters. """
        url = self.list_path + '?exclude_utm=1'
        program = self.create_program()
        self.assert_list_results(url, [program], 12, extra_context={'exclude_utm': 1})

    def test_minimal_serializer_use(self):
        """ Verify that the list view uses the minimal serializer. """
        self.assertEqual(ProgramViewSet(action='list').get_serializer_class(), MinimalProgramSerializer)
