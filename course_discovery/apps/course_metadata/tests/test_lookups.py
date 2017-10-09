import json
from urllib.parse import quote

import pytest
from django.test import TestCase
from django.urls import reverse

from course_discovery.apps.api.tests.mixins import SiteMixin
from course_discovery.apps.core.tests.factories import USER_PASSWORD, UserFactory
from course_discovery.apps.course_metadata.tests.factories import (
    CourseFactory, CourseRunFactory, OrganizationFactory, PersonFactory, PositionFactory
)
from course_discovery.apps.publisher.tests import factories


# pylint: disable=no-member


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

    def setUp(self):
        super(AutoCompletePersonTests, self).setUp()
        self.user = UserFactory(is_staff=True)
        self.client.login(username=self.user.username, password=USER_PASSWORD)
        self.courses = factories.CourseFactory.create_batch(3, title='Some random course title')

        for course in self.courses:
            factories.CourseRunFactory(course=course)

        self.organizations = OrganizationFactory.create_batch(3)
        self.organization_extensions = []

        for organization in self.organizations:
            self.organization_extensions.append(factories.OrganizationExtensionFactory(organization=organization))

        self.user.groups.add(self.organization_extensions[0].group)
        first_instructor = PersonFactory(given_name="First Instructor")
        second_instructor = PersonFactory(given_name="Second Instructor")
        self.instructors = [first_instructor, second_instructor]

        for instructor in self.instructors:
            PositionFactory(organization=self.organizations[0], title="professor", person=instructor)

    def test_instructor_autocomplete(self):
        """ Verify instructor autocomplete returns the data. """
        response = self.client.get(
            reverse('admin_metadata:person-autocomplete') + '?q={q}'.format(q='ins')
        )
        self._assert_response(response, 2)

        # update first instructor's name
        self.instructors[0].given_name = 'dummy_name'
        self.instructors[0].save()

        response = self.client.get(
            reverse('admin_metadata:person-autocomplete') + '?q={q}'.format(q='dummy')
        )
        self._assert_response(response, 1)

    def test_instructor_autocomplete_un_authorize_user(self):
        """ Verify instructor autocomplete returns empty list for un-authorized users. """
        self._make_user_non_staff()
        response = self.client.get(reverse('admin_metadata:person-autocomplete'))
        self._assert_response(response, 0)

    def test_instructor_position_in_label(self):
        """ Verify that instructor label contains position of instructor if it exists."""
        position_title = 'professor'

        response = self.client.get(
            reverse('admin_metadata:person-autocomplete') + '?q={q}'.format(q='ins')
        )

        self.assertContains(response, '<p>{position} at {organization}</p>'.format(
            position=position_title,
            organization=self.organizations[0].name))

    def test_instructor_image_in_label(self):
        """ Verify that instructor label contains profile image url."""
        response = self.client.get(
            reverse('admin_metadata:person-autocomplete') + '?q={q}'.format(q='ins')
        )
        self.assertContains(response, self.instructors[0].get_profile_image_url)
        self.assertContains(response, self.instructors[1].get_profile_image_url)

    def _assert_response(self, response, expected_length):
        """ Assert autocomplete response. """
        assert response.status_code == 200
        data = json.loads(response.content.decode('utf-8'))
        assert len(data['results']) == expected_length

    def test_instructor_autocomplete_with_uuid(self):
        """ Verify instructor autocomplete returns the data with valid uuid. """
        uuid = self.instructors[0].uuid
        response = self.client.get(
            reverse('admin_metadata:person-autocomplete') + '?q={q}'.format(q=uuid)
        )
        self._assert_response(response, 1)

    def test_instructor_autocomplete_with_invalid_uuid(self):
        """ Verify instructor autocomplete returns empty list without giving error. """
        uuid = 'invalid-uuid'
        response = self.client.get(
            reverse('admin_metadata:person-autocomplete') + '?q={q}'.format(q=uuid)
        )
        self._assert_response(response, 0)

    def test_instructor_autocomplete_without_staff_user(self):
        """ Verify instructor autocomplete returns the data if user is not staff. """
        non_staff_user = UserFactory()
        non_staff_user.groups.add(self.organization_extensions[0].group)
        self.client.logout()
        self.client.login(username=non_staff_user.username, password=USER_PASSWORD)

        response = self.client.get(
            reverse('admin_metadata:person-autocomplete') + '?q={q}'.format(q='ins')
        )
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

        response = self.client.get(
            reverse('admin_metadata:person-autocomplete') + '?q={q}'.format(q='ins'),
            HTTP_REFERER=reverse('admin:publisher_courserun_add')
        )
        assert response.status_code == 200
        data = json.loads(response.content.decode('utf-8'))
        expected_results = [{'id': instructor.id, 'text': str(instructor)} for instructor in self.instructors]
        assert data.get('results') == expected_results

    def _make_user_non_staff(self):
        self.client.logout()
        self.user = UserFactory(is_staff=False)
        self.user.save()
        self.client.login(username=self.user.username, password=USER_PASSWORD)
