import json
from urllib.parse import quote

import pytest
from django.test import TestCase
from django.urls import reverse

from course_discovery.apps.api.tests.mixins import SiteMixin
from course_discovery.apps.core.tests.factories import USER_PASSWORD, UserFactory
from course_discovery.apps.course_metadata.tests.factories import (
    CourseFactory, CourseRunFactory, OrganizationFactory, PersonFactory, PositionFactory, ProgramFactory
)
from course_discovery.apps.publisher.tests.factories import OrganizationExtensionFactory


@pytest.mark.django_db
class TestAutocomplete:
    def assert_valid_query_result(self, client, path, query, expected_result):
        """ Asserts a query made against the given endpoint returns the expected result. """
        response = client.get(path + '?q={q}'.format(q=query))
        data = json.loads(response.content.decode('utf-8'))
        assert len(data['results']) == 1
        assert data['results'][0]['text'] == str(expected_result)

    def test_course_autocomplete(self, admin_client):
        """ Verify course autocomplete returns the data. """
        courses = CourseFactory.create_batch(3)
        path = reverse('admin_metadata:course-autocomplete')
        response = admin_client.get(path)
        data = json.loads(response.content.decode('utf-8'))
        assert response.status_code == 200
        assert len(data['results']) == 3

        # Search for substrings of course keys and titles
        course = courses[0]
        self.assert_valid_query_result(admin_client, path, course.key[12:], course)
        self.assert_valid_query_result(admin_client, path, course.title[12:], course)

    def test_course_run_autocomplete(self, admin_client):
        course_runs = CourseRunFactory.create_batch(3)
        path = reverse('admin_metadata:course-run-autocomplete')
        response = admin_client.get(path)
        data = json.loads(response.content.decode('utf-8'))
        assert response.status_code == 200
        assert len(data['results']) == 3

        # Search for substrings of course run keys and titles
        course_run = course_runs[0]
        self.assert_valid_query_result(admin_client, path, course_run.key[14:], course_run)
        self.assert_valid_query_result(admin_client, path, course_run.title[12:], course_run)

        course = course_run.course
        CourseRunFactory.create_batch(3, course=course)
        response = admin_client.get(path + '?forward={f}'.format(f=json.dumps({'course': course.pk})))
        data = json.loads(response.content.decode('utf-8'))
        assert response.status_code == 200
        assert len(data['results']) == 4

    def test_program_autocomplete(self, admin_client):
        """ Verify Program autocomplete returns the data. """
        programs = ProgramFactory.create_batch(3)
        path = reverse('admin_metadata:program-autocomplete')
        response = admin_client.get(path)
        data = json.loads(response.content.decode('utf-8'))
        assert response.status_code == 200
        assert len(data['results']) == 3

        # Search for substrings of program titles
        program = programs[0]
        self.assert_valid_query_result(admin_client, path, program.title[5:], program)
        program = programs[1]
        self.assert_valid_query_result(admin_client, path, program.title[5:], program)

        admin_client.logout()
        response = admin_client.get(path)
        data = json.loads(response.content.decode('utf-8'))
        assert response.status_code == 200
        assert not data['results']

    def test_organization_autocomplete(self, admin_client):
        """ Verify Organization autocomplete returns the data. """
        organizations = OrganizationFactory.create_batch(3)
        path = reverse('admin_metadata:organisation-autocomplete')
        response = admin_client.get(path)
        data = json.loads(response.content.decode('utf-8'))
        assert response.status_code == 200
        assert len(data['results']) == 3

        # Search for substrings of organization keys and names
        organization = organizations[0]
        self.assert_valid_query_result(admin_client, path, organization.key[:3], organization)
        self.assert_valid_query_result(admin_client, path, organization.name[:5], organization)

    @pytest.mark.parametrize('view_prefix', ['organisation', 'course', 'course-run'])
    def test_autocomplete_requires_staff_permission(self, view_prefix, client):
        """ Verify autocomplete returns empty list for non-staff users. """

        user = UserFactory(is_staff=False)
        client.login(username=user.username, password=USER_PASSWORD)
        response = client.get(reverse('admin_metadata:{}-autocomplete'.format(view_prefix)))
        data = json.loads(response.content.decode('utf-8'))
        assert response.status_code == 200
        assert data['results'] == []


class AutoCompletePersonTests(SiteMixin, TestCase):
    """
    Tests for person autocomplete lookups
    """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.user = UserFactory(is_staff=True)

        first_instructor = PersonFactory(given_name="First", family_name="Instructor")
        second_instructor = PersonFactory(given_name="Second", family_name="Instructor")
        cls.instructors = [first_instructor, second_instructor]

        cls.organizations = OrganizationFactory.create_batch(3)
        cls.organization_extensions = []

        for instructor in cls.instructors:
            PositionFactory(organization=cls.organizations[0], title="professor", person=instructor)

        for organization in cls.organizations:
            cls.organization_extensions.append(OrganizationExtensionFactory(organization=organization))

        disco_course = CourseFactory(authoring_organizations=[cls.organizations[0]])
        disco_course2 = CourseFactory(authoring_organizations=[cls.organizations[1]])
        CourseRunFactory(course=disco_course, staff=[first_instructor])
        CourseRunFactory(course=disco_course2, staff=[second_instructor])

        cls.user.groups.add(cls.organization_extensions[0].group)

    def setUp(self):
        super().setUp()
        self._set_user_is_staff_and_login(True)

    def query(self, q):
        query_params = '?q={q}'.format(q=q)

        return self.client.get(
            reverse('admin_metadata:person-autocomplete') + query_params
        )

    def test_instructor_autocomplete(self):
        """ Verify instructor autocomplete returns the data. """
        response = self.query('ins')
        self._assert_response(response, 2)

        # look for the name of the first instructor
        response = self.query('First')
        self._assert_response(response, 1)

    def test_instructor_autocomplete_un_authorize_user(self):
        """ Verify instructor autocomplete returns empty list for un-authorized users. """
        self._set_user_is_staff_and_login(False)
        response = self.client.get(reverse('admin_metadata:person-autocomplete'))
        self._assert_response(response, 0)

    def test_instructor_autocomplete_spaces(self):
        """ Verify instructor autocomplete allows spaces. """
        response = self.query('sec ins')
        self._assert_response(response, 1)

    def test_instructor_autocomplete_no_results(self):
        """ Verify instructor autocomplete correctly finds no matches if string doesn't match. """
        response = self.query('second nope')
        self._assert_response(response, 0)

    def test_instructor_autocomplete_last_name_first_name(self):
        """ Verify instructor autocomplete allows last name first. """
        response = self.query('instructor first')
        self._assert_response(response, 1)

    def _assert_response(self, response, expected_length):
        """ Assert autocomplete response. """
        assert response.status_code == 200
        data = json.loads(response.content.decode('utf-8'))
        assert len(data['results']) == expected_length

    def test_instructor_autocomplete_with_uuid(self):
        """ Verify instructor autocomplete returns the data with valid uuid. """
        uuid = self.instructors[0].uuid
        response = self.query(uuid)
        self._assert_response(response, 1)

    def test_instructor_autocomplete_with_invalid_uuid(self):
        """ Verify instructor autocomplete returns empty list without giving error. """
        uuid = 'invalid-uuid'
        response = self.query(uuid)
        self._assert_response(response, 0)

    def test_instructor_autocomplete_without_staff_user(self):
        """ Verify instructor autocomplete returns the data if user is not staff. """
        non_staff_user = UserFactory()
        non_staff_user.groups.add(self.organization_extensions[0].group)
        self.client.logout()
        self.client.login(username=non_staff_user.username, password=USER_PASSWORD)

        response = self.query('ins')
        self._assert_response(response, 2)

    def test_instructor_autocomplete_without_login(self):
        """ Verify instructor autocomplete returns the zero record if user is not logged in. """
        self.client.logout()
        person_autocomplete_url = reverse(
            'admin_metadata:person-autocomplete'
        ) + '?q={q}'.format(q=self.instructors[0].uuid)

        response = self.client.get(person_autocomplete_url)

        self.assertRedirects(
            response,
            expected_url='{url}?next={next}'.format(url=reverse('login'), next=quote(person_autocomplete_url)),
            status_code=302,
            target_status_code=302
        )

    def test_instructor_autocomplete_from_django_admin(self):
        """ Verify instructor autocomplete return default data from django admin. """
        admin_user = UserFactory(is_staff=True, is_superuser=True)
        self.client.logout()
        self.client.login(username=admin_user.username, password=USER_PASSWORD)

        response = self.client.get(reverse('admin_metadata:person-autocomplete') + '?q={q}'.format(q='ins'))
        assert response.status_code == 200
        data = json.loads(response.content.decode('utf-8'))
        expected_results = [{'id': str(instructor.id), 'text': str(instructor), 'selected_text': str(instructor)}
                            for instructor in self.instructors]

        assert (sorted(data.get('results'), key=lambda x: sorted(x.keys())) ==
                sorted(expected_results, key=lambda x: sorted(x.keys())))

    def _set_user_is_staff_and_login(self, is_staff=True):
        self.client.logout()
        self.user.is_staff = is_staff
        self.user.save()
        self.client.login(username=self.user.username, password=USER_PASSWORD)
