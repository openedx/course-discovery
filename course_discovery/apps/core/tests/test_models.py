""" Tests for core models. """

from django.test import TestCase
from social.apps.django_app.default.models import UserSocialAuth

from course_discovery.apps.core.models import Currency, Partner
from course_discovery.apps.core.tests.factories import UserFactory


class UserTests(TestCase):
    """ User model tests. """

    def setUp(self):
        super(UserTests, self).setUp()
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
        expected = "{first_name} {last_name}".format(first_name=first_name, last_name=last_name)
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
        self.assertEqual(str(instance), '{code} - {name}'.format(code=code, name=name))


class PartnerTests(TestCase):
    """ Tests for the Partner class. """

    def test_str(self):
        """
        Verify casting an instance to a string returns a string containing the name and short code of the partner.
        """

        code = 'test'
        name = 'Test Partner'
        instance = Partner(name=name, short_code=code)
        self.assertEqual(str(instance), '{name} ({code})'.format(name=name, code=code))
