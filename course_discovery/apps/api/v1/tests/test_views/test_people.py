from unittest import mock

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group, Permission
from django.db import IntegrityError
from rest_framework.reverse import reverse
from testfixtures import LogCapture
from waffle.testutils import override_switch

from course_discovery.apps.api.v1.tests.test_views.mixins import APITestCase, SerializationMixin
from course_discovery.apps.api.v1.views.people import logger as people_logger
from course_discovery.apps.core.tests.factories import USER_PASSWORD, UserFactory
from course_discovery.apps.course_metadata.models import Person, Position
from course_discovery.apps.course_metadata.people import MarketingSitePeople
from course_discovery.apps.course_metadata.tests.factories import (
    CourseFactory, CourseRunFactory, OrganizationFactory, PersonAreaOfExpertiseFactory, PersonFactory,
    PersonSocialNetworkFactory, PositionFactory
)

User = get_user_model()


@override_switch('publish_person_to_marketing_site', True)
class PersonViewSetTests(SerializationMixin, APITestCase):
    """ Tests for the person resource. """
    people_list_url = reverse('api:v1:person-list')

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls._original_partner_marketing_site_api_username = cls.partner.marketing_site_api_username

    def setUp(self):
        super().setUp()
        self.user = UserFactory()
        self.request.user = self.user
        self.target_permissions = Permission.objects.filter(
            codename__in=['add_person', 'change_person', 'delete_person']
        )
        self.internal_test_group = Group.objects.create(name='internal-test')
        self.internal_test_group.permissions.add(*self.target_permissions)
        self.user.groups.add(self.internal_test_group)
        self.client.login(username=self.user.username, password=USER_PASSWORD)
        with override_switch('publish_person_to_marketing_site', False):
            self.person = PersonFactory(partner=self.partner)
        self.organization = OrganizationFactory(partner=self.partner)
        PositionFactory(person=self.person, organization=self.organization)
        self.expected_node = {
            'resource': 'node',
            'id': '28691',
            'uuid': '18d5542f-fa80-418e-b416-455cfdeb4d4e',
            'uri': 'https://stage.edx.org/node/28691'
        }

        self.partner.marketing_site_api_username = self._original_partner_marketing_site_api_username
        self.partner.save()

    def person_exists(self, data):
        return Person.objects.filter(
            given_name=data['given_name'], family_name=data['family_name'], bio=data['bio']
        ).exists()

    def test_create_with_authentication(self):
        """ Verify endpoint successfully creates a person. """
        with mock.patch.object(MarketingSitePeople, 'update_or_publish_person', return_value=self.expected_node):
            response = self.client.post(self.people_list_url, self._person_data(), format='json')
            self.assertEqual(response.status_code, 201)

        data = self._person_data()
        person = Person.objects.last()
        self.assertDictEqual(response.data, self.serialize_person(person))
        self.assertEqual(person.given_name, data['given_name'])
        self.assertEqual(person.family_name, data['family_name'])
        self.assertEqual(person.bio, data['bio'])
        self.assertEqual(person.position.title, data['position']['title'])
        self.assertEqual(person.position.organization, self.organization)
        self.assertEqual(person.major_works, data['major_works'])
        self.assertListEqual(
            sorted([social_network.url for social_network in person.person_networks.all()]),
            sorted([url_detailed['url'] for url_detailed in data['urls_detailed']])
        )
        self.assertListEqual(
            sorted([social_network.title for social_network in person.person_networks.all()]),
            sorted([url_detailed['title'] for url_detailed in data['urls_detailed']])
        )

        # Test display_title
        # Test that empty string titles get changed to type when looking at display title for not OTHERS
        self.assertEqual('Facebook', person.person_networks.get(type='facebook', title='').display_title)
        # Test that defined titles are shown
        self.assertEqual(
            'Hopkins Twitter', person.person_networks.get(type='twitter', title='Hopkins Twitter').display_title
        )
        self.assertEqual('blog', person.person_networks.get(type='blog', title='blog').display_title)
        # Test that empty string titles get changed to url when looking at display title for OTHERS
        self.assertEqual(
            'http://www.others.com/hopkins', person.person_networks.get(type='others', title='').display_title
        )

        self.assertListEqual(
            sorted([area_of_expertise.value for area_of_expertise in person.areas_of_expertise.all()]),
            sorted([area_of_expertise['value'] for area_of_expertise in data['areas_of_expertise']])
        )

    def test_create_without_drupal_client_settings(self):
        """ Verify that if credentials are missing api will return the error. """
        self.partner.marketing_site_api_username = None
        self.partner.save()
        data = self._person_data()

        with LogCapture(people_logger.name) as log_capture:
            response = self.client.post(self.people_list_url, self._person_data(), format='json')
            self.assertEqual(response.status_code, 400)
            log_capture.check(
                (
                    people_logger.name,
                    'ERROR',
                    'An error occurred while adding the person [{}]-[{}] to the marketing site.'.format(
                        data['given_name'], data['family_name']
                    )
                )
            )

        self.assertFalse(self.person_exists(data))

    def test_create_with_api_exception(self):
        """ Verify that after creating drupal page if serializer fail due to any error, message
        will be logged and drupal page will be deleted. """

        data = self._person_data()
        with mock.patch.object(MarketingSitePeople, 'update_or_publish_person', return_value=self.expected_node):
            with mock.patch(
                'course_discovery.apps.api.v1.views.people.PersonViewSet.perform_create',
                side_effect=IntegrityError
            ):
                with mock.patch.object(MarketingSitePeople, 'delete_person', return_value=None):
                    with LogCapture(people_logger.name) as log_capture:
                        response = self.client.post(self.people_list_url, self._person_data(), format='json')
                        self.assertEqual(response.status_code, 400)
                        log_capture.check(
                            (
                                people_logger.name,
                                'ERROR',
                                'An error occurred while adding the person [{}]-[{}] in discovery.'.format(
                                    data['given_name'], data['family_name'],
                                )
                            )
                        )

        self.assertFalse(self.person_exists(data))

    def test_create_without_authentication(self):
        """ Verify authentication is required when creating a person. """
        self.client.logout()
        Person.objects.all().delete()

        response = self.client.post(self.people_list_url)
        assert response.status_code == 401
        assert Person.objects.count() == 0

    def test_create_without_permission(self):
        """ Verify group is required when creating a person. """
        self.client.logout()
        new_user = UserFactory()
        new_user.groups.clear()
        self.client.login(username=new_user.username, password=USER_PASSWORD)
        current_people_count = Person.objects.count()
        response = self.client.post(self.people_list_url)
        assert response.status_code == 403
        assert Person.objects.count() == current_people_count

    def test_get_single_person_with_publisher_user(self):
        """ Verify the endpoint returns the details for a single person. """
        url = reverse('api:v1:person-detail', kwargs={'uuid': self.person.uuid})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertDictEqual(response.data, self.serialize_person(self.person))

    def test_get_without_authentication(self):
        """ Verify the endpoint allows viewing the details for a single person unauthenticated """
        self.client.logout()
        url = reverse('api:v1:person-detail', kwargs={'uuid': self.person.uuid})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertDictEqual(response.data, self.serialize_person(self.person))

    def test_list_with_publisher_user(self):
        """ Verify the endpoint returns a list of all people with the publisher user """
        response = self.client.get(self.people_list_url)
        self.assertEqual(response.status_code, 200)
        self.assertCountEqual(response.data['results'], self.serialize_person(Person.objects.all(), many=True))

    def test_list_different_partner(self):
        """ Verify the endpoint only shows people for the current partner. """
        with mock.patch.object(MarketingSitePeople, 'update_or_publish_person'):
            PersonFactory()  # create person for a partner that isn't self.partner; we expect this to not show up later
        response = self.client.get(self.people_list_url)
        self.assertEqual(response.status_code, 200)
        # Make sure the list does not include the new person above
        self.assertCountEqual(response.data['results'], self.serialize_person([self.person], many=True))

    def test_list_filter_by_slug(self):
        """ Verify the endpoint allows people to be filtered by slug. """
        with mock.patch.object(MarketingSitePeople, 'update_or_publish_person'):
            person = PersonFactory(partner=self.partner)
        url = f'{self.people_list_url}?slug={person.slug}'
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertCountEqual(response.data['results'], self.serialize_person([person], many=True))

    def test_list_filter_by_slug_unauthenticated(self):
        """ Verify the endpoint allows people to be filtered by slug, unauthenticated """
        self.client.logout()
        with mock.patch.object(MarketingSitePeople, 'update_or_publish_person'):
            person = PersonFactory(partner=self.partner)
        url = f'{self.people_list_url}?slug={person.slug}'
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertCountEqual(response.data['results'], self.serialize_person([person], many=True))

    def test_with_no_org(self):
        org1 = OrganizationFactory()
        course = CourseFactory(authoring_organizations=[org1])
        with mock.patch.object(MarketingSitePeople, 'update_or_publish_person'):
            person1 = PersonFactory(partner=self.partner)
            PersonFactory(partner=self.partner)
            CourseRunFactory(staff=[person1], course=course)
            url = f'{self.people_list_url}?org='
            response = self.client.get(url)
            self.assertEqual(response.status_code, 200)
            self.assertEqual(len(response.data['results']), 0)

    def test_list_with_org_single(self):
        org1 = OrganizationFactory()
        course = CourseFactory(authoring_organizations=[org1])
        with mock.patch.object(MarketingSitePeople, 'update_or_publish_person'):
            person1 = PersonFactory(partner=self.partner)
            PersonFactory(partner=self.partner)
            PersonFactory(partner=self.partner)
            CourseRunFactory(staff=[person1], course=course)
            url = f'{self.people_list_url}?org={org1.key}'
            response = self.client.get(url)
            self.assertEqual(response.status_code, 200)
            self.assertEqual(len(response.data['results']), 1)
            self.assertEqual(response.data['results'], self.serialize_person([person1], many=True))

    def test_list_with_org_multiple(self):
        org1 = OrganizationFactory()
        org2 = OrganizationFactory()
        course1 = CourseFactory(authoring_organizations=[org1])
        course2 = CourseFactory(authoring_organizations=[org2])
        with mock.patch.object(MarketingSitePeople, 'update_or_publish_person'):
            person1 = PersonFactory(partner=self.partner)
            person2 = PersonFactory(partner=self.partner)
            PersonFactory(partner=self.partner)
            CourseRunFactory(staff=[person1], course=course1)
            CourseRunFactory(staff=[person2], course=course2)
            url = '{url}?org={org1_key}&org={org2_key}'.format(
                url=self.people_list_url,
                org1_key=org1.key,
                org2_key=org2.key,
            )
            response = self.client.get(url)
            self.assertEqual(response.status_code, 200)
            self.assertEqual(len(response.data['results']), 2)
            self.assertCountEqual(response.data['results'], self.serialize_person([person1, person2], many=True))

    @override_switch('publish_person_to_marketing_site', False)
    def test_create_without_waffle_switch(self):
        """ Verify endpoint proceeds if waffle switch is disabled. """
        data = self._person_data()
        with mock.patch.object(MarketingSitePeople, 'update_or_publish_person') as cm:
            response = self.client.post(self.people_list_url, data, format='json')
            self.assertEqual(cm.call_count, 0)
        self.assertEqual(response.status_code, 201)
        self.assertTrue(self.person_exists(data))

    def _person_data(self):
        return {
            'given_name': "Robert",
            'family_name': "Ford",
            'bio': "<p>The maze is not for him.</p>",
            'position': {
                'title': "Park Director",
                'organization': self.organization.id
            },
            'major_works': '<p>Delores<br />\nTeddy<br />\nMaive</p>',
            'urls_detailed': [
                {
                    'id': '1',
                    'type': 'facebook',
                    'title': '',
                    'display_title': 'Facebook',
                    'url': 'http://www.facebook.com/hopkins',
                },
                {
                    'id': '2',
                    'type': 'twitter',
                    'title': 'Hopkins Twitter',
                    'display_title': 'Hopkins Twitter',
                    'url': 'http://www.twitter.com/hopkins',
                },
                {
                    'id': '3',
                    'type': 'blog',
                    'title': 'blog',
                    'display_title': 'blog',
                    'url': 'http://www.blog.com/hopkins',
                },
                {
                    'id': '4',
                    'type': 'others',
                    'title': '',
                    'display_title': 'http://www.others.com/hopkins',
                    'url': 'http://www.others.com/hopkins',
                },
            ],
            'areas_of_expertise': [
                {
                    'id': '1',
                    'value': 'area 1'
                },
                {
                    'id': '2',
                    'value': 'area 2'
                },
            ],
        }

    def _update_person_data(self):
        return {
            'given_name': "updated",
            'family_name': "name",
            'bio': "<p>updated bio</p>",
            'position': {
                'title': "new title",
                'organization': self.organization.id
            },
            'major_works': '<p>new works</p>',
            'urls_detailed': [
                {
                    'id': '1',
                    'type': 'facebook',
                    'title': '',
                    'display_title': 'Facebook',
                    'url': 'http://www.facebook.com/new',
                },
                {
                    'id': '2',
                    'type': 'twitter',
                    'title': 'Hopkins new Twitter',
                    'display_title': 'Hopkins new Twitter',
                    'url': 'http://www.twitter.com/new',
                },
                {
                    'id': '4',
                    'type': 'others',
                    'title': 'new others',
                    'display_title': 'new others',
                    'url': 'http://www.others.com/new',
                },
                {
                    'id': '',
                    'type': 'others',
                    'title': 'Create new',
                    'display_title': 'Create new',
                    'url': 'http://www.others.com/new',
                },
            ],
            'areas_of_expertise': [
                {
                    'id': '1',
                    'value': 'new area 1'
                },
                {
                    'id': '',
                    'value': 'area 3'
                },
            ],
        }

    def test_update_without_drupal_client_settings(self):
        """ Verify that if credentials are missing api will return the error. """
        url = reverse('api:v1:person-detail', kwargs={'uuid': self.person.uuid})
        self.partner.marketing_site_api_username = None
        self.partner.save()
        data = self._update_person_data()

        with LogCapture(people_logger.name) as log_capture:
            response = self.client.patch(url, data, format='json')
            self.assertEqual(response.status_code, 400)
            log_capture.check(
                (
                    people_logger.name,
                    'ERROR',
                    'An error occurred while updating the person [{}]-[{}] on the marketing site.'.format(
                        data['given_name'], data['family_name']
                    )
                )
            )

    def test_update_with_api_exception(self):
        """ Verify that if the serializer fails, error message is logged and update fails"""
        url = reverse('api:v1:person-detail', kwargs={'uuid': self.person.uuid})
        data = self._update_person_data()
        with mock.patch.object(MarketingSitePeople, 'update_or_publish_person', return_value={}):
            with mock.patch(
                'course_discovery.apps.api.v1.views.people.PersonViewSet.perform_update',
                side_effect=IntegrityError
            ):
                with LogCapture(people_logger.name) as log_capture:
                    response = self.client.patch(url, self._update_person_data(), format='json')
                    self.assertEqual(response.status_code, 400)
                    log_capture.check(
                        (
                            people_logger.name,
                            'ERROR',
                            'An error occurred while updating the person [{}]-[{}] in discovery.'.format(
                                data['given_name'], data['family_name']
                            )
                        )
                    )

    @override_switch('publish_person_to_marketing_site', False)
    def test_update_without_waffle_switch(self):
        """ Verify update endpoint proceeds if waffle switch is disabled. """
        url = reverse('api:v1:person-detail', kwargs={'uuid': self.person.uuid})
        data = self._update_person_data()
        with mock.patch.object(MarketingSitePeople, 'update_or_publish_person') as cm:
            response = self.client.patch(url, data, format='json')
            self.assertEqual(cm.call_count, 0)
        self.assertEqual(response.status_code, 200)
        self.assertTrue(self.person_exists(data))

    def test_update(self):
        """Verify that people data can be updated using endpoint."""
        url = reverse('api:v1:person-detail', kwargs={'uuid': self.person.uuid})

        data = self._update_person_data()

        # These are being created so we can verify they are deleted since they are not part of updated_data
        PersonSocialNetworkFactory(person=self.person, type='blog')
        removed_value = PersonAreaOfExpertiseFactory(person=self.person).value

        with mock.patch.object(MarketingSitePeople, 'update_or_publish_person', return_value={}):
            response = self.client.patch(url, data, format='json')
            self.assertEqual(response.status_code, 200)

        updated_person = Person.objects.get(id=self.person.id)

        self.assertEqual(updated_person.given_name, data['given_name'])
        self.assertEqual(updated_person.family_name, data['family_name'])
        self.assertEqual(updated_person.bio, data['bio'])
        self.assertEqual(updated_person.position.title, data['position']['title'])
        self.assertEqual(updated_person.major_works, data['major_works'])
        self.assertListEqual(
            sorted([social_network.url for social_network in updated_person.person_networks.all()]),
            sorted([url_detailed['url'] for url_detailed in data['urls_detailed']])
        )
        self.assertListEqual(
            sorted([social_network.title for social_network in updated_person.person_networks.all()]),
            sorted([url_detailed['title'] for url_detailed in data['urls_detailed']])
        )
        self.assertFalse(updated_person.person_networks.filter(type='blog').exists())

        # Test display_title
        # Test that empty string titles get changed to type when looking at display title for not OTHERS
        self.assertEqual('Facebook', updated_person.person_networks.get(type='facebook', title='').display_title)
        # Test that defined titles are shown
        self.assertEqual(
            'Hopkins new Twitter',
            updated_person.person_networks.get(type='twitter', title='Hopkins new Twitter').display_title
        )
        self.assertEqual(
            'new others', updated_person.person_networks.get(type='others', title='new others').display_title
        )
        self.assertEqual(
            'Create new', updated_person.person_networks.get(type='others', title='Create new').display_title
        )

        self.assertListEqual(
            sorted([area_of_expertise.value for area_of_expertise in updated_person.areas_of_expertise.all()]),
            sorted([area_of_expertise['value'] for area_of_expertise in data['areas_of_expertise']])
        )
        self.assertFalse(updated_person.areas_of_expertise.filter(value=removed_value).exists())

    def test_update_without_position(self):
        """
        Verify that if the people has no position a new position is created while updating people
        """
        url = reverse('api:v1:person-detail', kwargs={'uuid': self.person.uuid})

        data = self._update_person_data()
        Position.objects.all().delete()

        with mock.patch.object(MarketingSitePeople, 'update_or_publish_person', return_value={}):
            response = self.client.patch(url, data, format='json')
            self.assertEqual(response.status_code, 200)

        updated_person = Person.objects.get(id=self.person.id)

        self.assertEqual(updated_person.position.title, data['position']['title'])

    def test_update_with_org_restrictions(self):
        url = reverse('api:v1:person-detail', kwargs={'uuid': self.person.uuid})
        url = url + '?org=invalid-org'

        data = self._update_person_data()
        with mock.patch.object(MarketingSitePeople, 'update_or_publish_person', return_value={}):
            response = self.client.patch(url, data, format='json')
            self.assertEqual(response.status_code, 404)

        # Verify that the person wasn't updated.
        updated_person = Person.objects.get(id=self.person.id)
        self.assertEqual(updated_person.given_name, self.person.given_name)

    def test_options_org_choices(self):
        """ Verify that an OPTIONS request will provide a list of organizations. """

        self.organization.key = 'bbb'
        self.organization.name = 'Test'
        self.organization.save()
        org2 = OrganizationFactory(partner=self.partner, name='', key='aaa')

        response = self.client.options(self.people_list_url)
        self.assertEqual(response.status_code, 200)

        data = response.data['actions']['POST']
        self.assertEqual(
            data['position']['children']['organization']['choices'],
            [
                {'display_name': 'aaa', 'value': org2.id},
                {'display_name': 'bbb: Test', 'value': self.organization.id},
            ]
        )
