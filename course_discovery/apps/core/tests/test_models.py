""" Tests for core models. """
import ddt
import responses
from django.test import TestCase
from social_django.models import UserSocialAuth

from course_discovery.apps.core.models import Currency
from course_discovery.apps.core.tests.factories import PartnerFactory, UserFactory


class UserTests(TestCase):
    """ User model tests. """

    def setUp(self):
        super().setUp()
        self.user = UserFactory()

    def test_access_token_without_social_auth(self):
        """ Verify the property returns None if the user is not associated with a UserSocialAuth. """
        self.assertIsNone(self.user.access_token)

    def test_access_token(self):
        """ Verify the property returns the value of the access_token stored with the UserSocialAuth. """
        social_auth = UserSocialAuth.objects.create(user=self.user, provider='test', uid=self.user.username)
        self.assertIsNone(self.user.access_token)

        access_token = 'My voice is my passport. Verify me.'
        social_auth.extra_data.update({'access_token': access_token})
        social_auth.save()
        self.assertEqual(self.user.access_token, access_token)

    def test_get_full_name(self):
        """ Test that the user model concatenates first and last name if the full name is not set. """
        full_name = "George Costanza"
        user = UserFactory(full_name=full_name)
        self.assertEqual(user.get_full_name(), full_name)

        first_name = "Jerry"
        last_name = "Seinfeld"
        user = UserFactory(full_name=None, first_name=first_name, last_name=last_name)
        expected = f"{first_name} {last_name}"
        self.assertEqual(user.get_full_name(), expected)

        user = UserFactory(full_name=full_name, first_name=first_name, last_name=last_name)
        self.assertEqual(user.get_full_name(), full_name)


class CurrencyTests(TestCase):
    """ Tests for the Currency class. """

    def test_str(self):
        """ Verify casting an instance to a string returns a string containing the ID and name of the currency. """

        code = 'USD'
        name = 'U.S. Dollar'
        instance = Currency(code=code, name=name)
        self.assertEqual(str(instance), f'{code} - {name}')


@ddt.ddt
class PartnerTests(TestCase):
    """ Tests for the Partner class. """

    def test_str(self):
        """ Verify the method returns the name of the Partner. """

        partner = PartnerFactory()
        self.assertEqual(str(partner), partner.name)

    @ddt.unpack
    @ddt.data(
        ('', False),
        (None, False),
        ('https://example.com', True),
    )
    def test_has_marketing_site(self, marketing_site_url_root, expected):
        partner = PartnerFactory(marketing_site_url_root=marketing_site_url_root)
        self.assertEqual(partner.has_marketing_site, expected)

    @responses.activate
    def test_access_token(self):
        """ Verify the property retrieves, and caches, an access token from the OAuth 2.0 provider. """
        token = 'abc123'
        partner = PartnerFactory()
        url = f'{partner.oauth2_provider_url}/access_token'
        body = {
            'access_token': token,
            'expires_in': 3600,
        }
        responses.add(responses.POST, url, json=body, status=200)
        assert partner.access_token == token
        assert len(responses.calls) == 1

        # No HTTP calls should be made if the access token is cached.
        responses.reset()
        assert partner.access_token == token
