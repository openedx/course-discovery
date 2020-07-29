import json
import urllib.parse

import pytest
from django.test import RequestFactory
from django.urls import reverse

from course_discovery.apps.api.serializers import MinimalProgramSerializer
from course_discovery.apps.api.v1.tests.test_views.mixins import FuzzyInt, SerializationMixin
from course_discovery.apps.api.v1.views.programs import ProgramViewSet
from course_discovery.apps.core.tests.factories import USER_PASSWORD, UserFactory
from course_discovery.apps.core.tests.helpers import make_image_file
from course_discovery.apps.course_metadata.choices import ProgramStatus
from course_discovery.apps.course_metadata.models import Program
from course_discovery.apps.course_metadata.tests.factories import (
    CorporateEndorsementFactory, CourseFactory, CourseRunFactory, EndorsementFactory, ExpectedLearningItemFactory,
    JobOutlookItemFactory, OrganizationFactory, PersonFactory, ProgramFactory, VideoFactory
)


@pytest.mark.django_db
@pytest.mark.usefixtures('django_cache')
class TestProgramViewSet(SerializationMixin):
    client = None
    django_assert_num_queries = None
    list_path = reverse('api:v1:program-list')
    partner = None
    request = None

    @pytest.fixture(autouse=True)
    def setup(self, client, django_assert_num_queries, partner):
        user = UserFactory(is_staff=True, is_superuser=True)

        client.login(username=user.username, password=USER_PASSWORD)

        site = partner.site
        request = RequestFactory(SERVER_NAME=site.domain).get('')
        request.site = site
        request.user = user

        self.client = client
        self.django_assert_num_queries = django_assert_num_queries
        self.partner = partner
        self.request = request

    def _program_data(self):
        course_runs = CourseRunFactory.create_batch(3)
        organizations = OrganizationFactory.create_batch(3)
        return {
            "title": "Test Program",
            "type": "XSeries",
            "status": "active",
            "marketing_slug": "edX-test-program",
            "course_runs": [course_run.key for course_run in course_runs],
            "min_hours_effort_per_week": 10,
            "max_hours_effort_per_week": 20,
            "authoring_organizations": [organization.key for organization in organizations],
            "credit_backing_organizations": [organization.key for organization in organizations],
        }

    def create_program(self):
        organizations = [OrganizationFactory(partner=self.partner)]
        person = PersonFactory()

        course = CourseFactory(partner=self.partner)
        CourseRunFactory(course=course, staff=[person])

        program = ProgramFactory(
            courses=[course],
            authoring_organizations=organizations,
            credit_backing_organizations=organizations,
            corporate_endorsements=CorporateEndorsementFactory.create_batch(1),
            individual_endorsements=EndorsementFactory.create_batch(1),
            expected_learning_items=ExpectedLearningItemFactory.create_batch(1),
            job_outlook_items=JobOutlookItemFactory.create_batch(1),
            instructor_ordering=PersonFactory.create_batch(1),
            banner_image=make_image_file('test_banner.jpg'),
            video=VideoFactory(),
            partner=self.partner
        )
        return program

    def assert_retrieve_success(self, program, querystring=None):
        """ Verify the retrieve endpoint succesfully returns a serialized program. """
        url = reverse('api:v1:program-detail', kwargs={'uuid': program.uuid})

        if querystring:
            url += '?' + urllib.parse.urlencode(querystring)

        response = self.client.get(url)
        assert response.status_code == 200
        return response

    def test_authentication(self):
        """ Verify the endpoint requires the user to be authenticated. """
        response = self.client.get(self.list_path)
        assert response.status_code == 200

        self.client.logout()
        response = self.client.get(self.list_path)
        assert response.status_code == 403

    def test_retrieve(self, django_assert_num_queries):
        """ Verify the endpoint returns the details for a single program. """
        program = self.create_program()

        with django_assert_num_queries(FuzzyInt(60, 2)):
            response = self.assert_retrieve_success(program)
        # property does not have the right values while being indexed
        del program._course_run_weeks_to_complete
        assert response.data == self.serialize_program(program)

        # Verify that requests including querystring parameters are cached separately.
        response = self.assert_retrieve_success(program, querystring={'use_full_course_serializer': 1})
        assert response.data == self.serialize_program(program, extra_context={'use_full_course_serializer': 1})

    @pytest.mark.parametrize('order_courses_by_start_date', (True, False,))
    def test_retrieve_with_sorting_flag(self, order_courses_by_start_date, django_assert_num_queries):
        """ Verify the number of queries is the same with sorting flag set to true. """
        course_list = CourseFactory.create_batch(3, partner=self.partner)
        for course in course_list:
            CourseRunFactory(course=course)
        program = ProgramFactory(
            courses=course_list,
            order_courses_by_start_date=order_courses_by_start_date,
            partner=self.partner)
        # property does not have the right values while being indexed
        del program._course_run_weeks_to_complete
        with django_assert_num_queries(FuzzyInt(42, 2)):
            response = self.assert_retrieve_success(program)
        assert response.data == self.serialize_program(program)
        assert course_list == list(program.courses.all())  # pylint: disable=no-member

    def test_retrieve_without_course_runs(self, django_assert_num_queries):
        """ Verify the endpoint returns data for a program even if the program's courses have no course runs. """
        course = CourseFactory(partner=self.partner)
        program = ProgramFactory(courses=[course], partner=self.partner)
        with django_assert_num_queries(FuzzyInt(27, 2)):
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
        with self.django_assert_num_queries(FuzzyInt(expected_query_count, 2)):
            response = self.client.get(url)

        assert response.data['results'] == self.serialize_program(expected, many=True, extra_context=extra_context)

    def test_list(self):
        """ Verify the endpoint returns a list of all programs. """
        expected = [self.create_program() for __ in range(3)]
        expected.reverse()

        self.assert_list_results(self.list_path, expected, 28)

    def test_edx_org_short_name_filter(self):
        """
        Verify programs filtering on edX organization.
        """
        edx_org_short_name = 'edx'
        programs_api_url_with_org_filter = '{programs_api_url}?org={edx_org_short_name}'.format(
            programs_api_url=self.list_path,
            edx_org_short_name=edx_org_short_name
        )
        expected_serialized_programs = self.serialize_program(
            Program.objects.filter(authoring_organizations__key=edx_org_short_name),
            many=True
        )

        response = self.client.get(programs_api_url_with_org_filter)
        assert response.status_code == 200
        programs_from_response = response.data['results']
        assert programs_from_response == expected_serialized_programs

    def test_uuids_only(self):
        """
        Verify that the list view returns a simply list of UUIDs when the
        uuids_only query parameter is passed.
        """
        active = ProgramFactory.create_batch(3, partner=self.partner)
        retired = [ProgramFactory(status=ProgramStatus.Retired, partner=self.partner)]
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
        program = ProgramFactory(type__name=program_type_name, partner=self.partner)
        url = self.list_path + '?type=' + program_type_name
        self.assert_list_results(url, [program], 11)

        url = self.list_path + '?type=bar'
        self.assert_list_results(url, [], 5)

    def test_filter_by_types(self):
        """ Verify that the endpoint filters programs to those matching the provided ProgramType slugs. """
        expected = ProgramFactory.create_batch(2, partner=self.partner)
        expected.reverse()
        type_slugs = [p.type.slug for p in expected]
        url = self.list_path + '?types=' + ','.join(type_slugs)

        # Create a third program, which should be filtered out.
        ProgramFactory(partner=self.partner)

        self.assert_list_results(url, expected, 12)

    def test_filter_by_uuids(self):
        """ Verify that the endpoint filters programs to those matching the provided UUIDs. """
        expected = ProgramFactory.create_batch(2, partner=self.partner)
        expected.reverse()
        uuids = [str(p.uuid) for p in expected]
        url = self.list_path + '?uuids=' + ','.join(uuids)

        # Create a third program, which should be filtered out.
        ProgramFactory(partner=self.partner)

        self.assert_list_results(url, expected, 12)

    @pytest.mark.parametrize(
        'status,is_marketable,expected_query_count',
        (
            (ProgramStatus.Unpublished, False, 5),
            (ProgramStatus.Active, True, 13),
        )
    )
    def test_filter_by_marketable(self, status, is_marketable, expected_query_count):
        """ Verify the endpoint filters programs to those that are marketable. """
        url = self.list_path + '?marketable=1'
        ProgramFactory(marketing_slug='', partner=self.partner)
        programs = ProgramFactory.create_batch(3, status=status, partner=self.partner)
        programs.reverse()

        expected = programs if is_marketable else []
        assert list(Program.objects.marketable()) == expected
        self.assert_list_results(url, expected, expected_query_count)

    def test_filter_by_status(self):
        """ Verify the endpoint allows programs to filtered by one, or more, statuses. """
        active = ProgramFactory(status=ProgramStatus.Active, partner=self.partner)
        retired = ProgramFactory(status=ProgramStatus.Retired, partner=self.partner)

        url = self.list_path + '?status=active'
        self.assert_list_results(url, [active], 11)

        url = self.list_path + '?status=retired'
        self.assert_list_results(url, [retired], 11)

        url = self.list_path + '?status=active&status=retired'
        self.assert_list_results(url, [retired, active], 12)

    def test_filter_by_hidden(self):
        """ Endpoint should filter programs by their hidden attribute value. """
        hidden = ProgramFactory(hidden=True, partner=self.partner)
        not_hidden = ProgramFactory(hidden=False, partner=self.partner)

        url = self.list_path + '?hidden=True'
        self.assert_list_results(url, [hidden], 11)

        url = self.list_path + '?hidden=False'
        self.assert_list_results(url, [not_hidden], 11)

        url = self.list_path + '?hidden=1'
        self.assert_list_results(url, [hidden], 11)

        url = self.list_path + '?hidden=0'
        self.assert_list_results(url, [not_hidden], 11)

    def test_filter_by_marketing_slug(self):
        """ The endpoint should support filtering programs by marketing slug. """
        SLUG = 'test-program'

        # This program should not be included in the results below because it never matches the filter.
        self.create_program()

        url = '{root}?marketing_slug={slug}'.format(root=self.list_path, slug=SLUG)
        self.assert_list_results(url, [], 5)

        program = self.create_program()
        program.marketing_slug = SLUG
        program.save()

        self.assert_list_results(url, [program], 20)

    def test_list_exclude_utm(self):
        """ Verify the endpoint returns marketing URLs without UTM parameters. """
        url = self.list_path + '?exclude_utm=1'
        program = self.create_program()
        self.assert_list_results(url, [program], 19, extra_context={'exclude_utm': 1})

    def test_minimal_serializer_use(self):
        """ Verify that the list view uses the minimal serializer. """
        assert ProgramViewSet(action='list').get_serializer_class() == MinimalProgramSerializer

    def test_create_using_api(self):
        """
        Verify endpoint successfully creates a program.
        """
        response = self.client.post(self.list_path, self._program_data(), format='json')
        assert response.status_code == 201
        program = Program.objects.last()
        assert program.title == response.data['title']
        assert program.status == response.data['status']
        assert program.courses.count() == 3
        assert program.authoring_organizations.count() == 3
        assert program.credit_backing_organizations.count() == 3

    def test_update_using_api(self):
        """
        Verify endpoint successfully updates a program.
        """
        program_data = self._program_data()

        response = self.client.post(self.list_path, program_data, format='json')
        assert response.status_code == 201
        program = Program.objects.last()
        assert program.courses.count() == 3
        assert program.authoring_organizations.count() == 3
        assert program.credit_backing_organizations.count() == 3

        program_detail_url = reverse('api:v1:program-detail', kwargs={'uuid': str(program.uuid)})
        program.title = '{orignal_title} Test Update'.format(orignal_title=program_data['title'])
        program_data['status'] = 'unpublished'

        course_runs = CourseRunFactory.create_batch(2)
        course_runs = [course_run.key for course_run in course_runs]
        program_data['course_runs'] = program_data['course_runs'] + course_runs

        organizations = OrganizationFactory.create_batch(3)
        organizations = [organization.key for organization in organizations]
        program_data['authoring_organizations'] = program_data['authoring_organizations'] + organizations
        program_data['credit_backing_organizations'] = program_data['credit_backing_organizations'] + organizations

        data = json.dumps(program_data)
        response = self.client.patch(program_detail_url, data, content_type='application/json')
        assert response.status_code == 200
        program = Program.objects.last()
        assert program.title == response.data['title']
        assert program.status == response.data['status']
        assert program.courses.count() == 5
        assert program.authoring_organizations.count() == 6
        assert program.credit_backing_organizations.count() == 6

        course_runs = CourseRunFactory.create_batch(2)
        course_runs = [course_run.key for course_run in course_runs]
        course_runs.append(program_data['course_runs'][0])
        program_data['course_runs'] = course_runs

        organizations = OrganizationFactory.create_batch(3)
        organizations = [organization.key for organization in organizations]
        organizations.append(program_data['authoring_organizations'][0])
        program_data['authoring_organizations'] = organizations
        program_data['credit_backing_organizations'] = organizations

        data = json.dumps(program_data)
        response = self.client.patch(program_detail_url, data, content_type='application/json')
        assert response.status_code == 200
        program = Program.objects.last()
        assert program.courses.count() == 3
        assert program.authoring_organizations.count() == 4
        assert program.credit_backing_organizations.count() == 4
