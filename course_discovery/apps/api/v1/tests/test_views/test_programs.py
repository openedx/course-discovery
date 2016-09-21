import ddt
from django.core.urlresolvers import reverse
from rest_framework.test import APITestCase, APIRequestFactory

from course_discovery.apps.api.serializers import ProgramSerializer
from course_discovery.apps.core.tests.factories import USER_PASSWORD, UserFactory
from course_discovery.apps.course_metadata.choices import ProgramStatus
from course_discovery.apps.course_metadata.models import Program
from course_discovery.apps.course_metadata.tests.factories import ProgramFactory, CourseFactory


@ddt.ddt
class ProgramViewSetTests(APITestCase):
    list_path = reverse('api:v1:program-list')

    def setUp(self):
        super(ProgramViewSetTests, self).setUp()
        self.user = UserFactory(is_staff=True, is_superuser=True)
        self.client.login(username=self.user.username, password=USER_PASSWORD)
        self.request = APIRequestFactory().get('/')
        self.request.user = self.user

    def assert_retrieve_success(self, program):
        """ Verify the retrieve endpoint succesfully returns a serialized program. """
        url = reverse('api:v1:program-detail', kwargs={'uuid': program.uuid})

        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data, ProgramSerializer(program, context={'request': self.request}).data)

    def test_authentication(self):
        """ Verify the endpoint requires the user to be authenticated. """
        response = self.client.get(self.list_path)
        self.assertEqual(response.status_code, 200)

        self.client.logout()
        response = self.client.get(self.list_path)
        self.assertEqual(response.status_code, 403)

    def test_retrieve(self):
        """ Verify the endpoint returns the details for a single program. """
        program = ProgramFactory()
        with self.assertNumQueries(33):
            self.assert_retrieve_success(program)

    def test_retrieve_without_course_runs(self):
        """ Verify the endpoint returns data for a program even if the program's courses have no course runs. """
        course = CourseFactory()
        program = ProgramFactory(courses=[course])
        with self.assertNumQueries(55):
            self.assert_retrieve_success(program)

    def assert_list_results(self, url, expected, expected_query_count):
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
            ProgramSerializer(expected, many=True, context={'request': self.request}).data
        )

    def test_list(self):
        """ Verify the endpoint returns a list of all programs. """
        expected = ProgramFactory.create_batch(3)
        expected.reverse()
        self.assert_list_results(self.list_path, expected, 14)

    def test_filter_by_type(self):
        """ Verify that the endpoint filters programs to those of a given type. """
        program_type_name = 'foo'
        program = ProgramFactory(type__name=program_type_name)
        url = self.list_path + '?type=' + program_type_name
        self.assert_list_results(url, [program], 14)

        url = self.list_path + '?type=bar'
        self.assert_list_results(url, [], 4)

    def test_filter_by_uuids(self):
        """ Verify that the endpoint filters programs to those matching the provided UUIDs. """
        expected = ProgramFactory.create_batch(2)
        expected.reverse()
        uuids = [str(p.uuid) for p in expected]
        url = self.list_path + '?uuids=' + ','.join(uuids)

        # Create a third program, which should be filtered out.
        ProgramFactory()

        self.assert_list_results(url, expected, 14)

    @ddt.data(
        (ProgramStatus.Unpublished, False, 4),
        (ProgramStatus.Active, True, 14),
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
