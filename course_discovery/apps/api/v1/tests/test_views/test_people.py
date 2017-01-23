# pylint: disable=redefined-builtin,no-member
import json

import ddt
from django.contrib.auth import get_user_model
from rest_framework.reverse import reverse
from rest_framework.test import APITestCase

from course_discovery.apps.api.v1.tests.test_views.mixins import SerializationMixin
from course_discovery.apps.core.tests.factories import UserFactory
from course_discovery.apps.course_metadata.models import Person
from course_discovery.apps.course_metadata.tests.factories import PersonFactory, OrganizationFactory

User = get_user_model()


@ddt.ddt
class PersonViewSetTests(SerializationMixin, APITestCase):
    """ Tests for the person resource. """
    people_list_url = reverse('api:v1:person-list')

    def setUp(self):
        super(PersonViewSetTests, self).setUp()
        self.user = UserFactory(is_staff=True, is_superuser=True)
        self.client.force_authenticate(self.user)
        self.person = PersonFactory()
        self.organization = OrganizationFactory()

    def test_create_with_authentication(self):
        """ Verify endpoint successfully creates a person. """
        given_name = "Robert"
        family_name = "Ford"
        bio = "The maze is not for him."
        title = "Park Director"
        organization_id = self.organization.id

        data = {
            'data': json.dumps(
                {
                    'given_name': given_name,
                    'family_name': family_name,
                    'bio': bio,
                    'position': {
                        'title': title,
                        'organization': organization_id
                    }
                }
            )
        }

        response = self.client.post(self.people_list_url, data, format='json')
        self.assertEqual(response.status_code, 201)

        person = Person.objects.last()
        self.assertDictEqual(response.data, self.serialize_person(person))
        self.assertEqual(person.given_name, given_name)
        self.assertEqual(person.family_name, family_name)
        self.assertEqual(person.bio, bio)
        self.assertEqual(person.position.title, title)
        self.assertEqual(person.position.organization, self.organization)

    def test_create_without_authentication(self):
        """ Verify authentication is required when creating a person. """
        self.client.logout()
        Person.objects.all().delete()

        response = self.client.post(self.people_list_url, {}, format='json')
        self.assertEqual(response.status_code, 403)
        self.assertEqual(Person.objects.count(), 0)

    def test_get(self):
        """ Verify the endpoint returns the details for a single person. """
        url = reverse('api:v1:person-detail', kwargs={'uuid': self.person.uuid})

        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data, self.serialize_person(self.person))

    def test_list(self):
        """ Verify the endpoint returns a list of all people. """
        response = self.client.get(self.people_list_url)
        self.assertEqual(response.status_code, 200)
        self.assertListEqual(response.data['results'], self.serialize_person(Person.objects.all(), many=True))
