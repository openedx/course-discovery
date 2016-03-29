""" Tests for core models. """

from django.test import TestCase
from django_dynamic_fixture import G
from social.apps.django_app.default.models import UserSocialAuth

from course_discovery.apps.core.models import User, Currency


# pylint: disable=no-member
class UserTests(TestCase):
    """ User model tests. """
    TEST_CONTEXT = {'foo': 'bar', 'baz': None}

    def test_access_token(self):
        user = G(User)
        self.assertIsNone(user.access_token)

        social_auth = G(UserSocialAuth, user=user)
        self.assertIsNone(user.access_token)

        access_token = u'My voice is my passport. Verify me.'
        social_auth.extra_data[u'access_token'] = access_token
        social_auth.save()
        self.assertEqual(user.access_token, access_token)

    def test_get_full_name(self):
        """ Test that the user model concatenates first and last name if the full name is not set. """
        full_name = "George Costanza"
        user = G(User, full_name=full_name)
        self.assertEqual(user.get_full_name(), full_name)

        first_name = "Jerry"
        last_name = "Seinfeld"
        user = G(User, full_name=None, first_name=first_name, last_name=last_name)
        expected = "{first_name} {last_name}".format(first_name=first_name, last_name=last_name)
        self.assertEqual(user.get_full_name(), expected)

        user = G(User, full_name=full_name, first_name=first_name, last_name=last_name)
        self.assertEqual(user.get_full_name(), full_name)


class CurrencyTests(TestCase):
    """ Tests for the Currency class. """

    def test_str(self):
        """ Verify casting an instance to a string returns a string containing the ID and name of the currency. """

        code = 'USD',
        name = 'U.S. Dollar'
        instance = Currency(code=code, name=name)
        self.assertEqual(str(instance), '{code} - {name}'.format(code=code, name=name))
