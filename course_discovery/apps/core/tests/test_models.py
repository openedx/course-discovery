""" Tests for core models. """

from django.test import TestCase
from django_dynamic_fixture import G
from social.apps.django_app.default.models import UserSocialAuth

from course_discovery.apps.core.models import User, Language, Locale, Currency


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


# pylint: disable=no-member
class LanguageTests(TestCase):
    """ Language model tests. """

    def test_str(self):
        iso_code = "en"
        language = Language(iso_code=iso_code)
        self.assertEqual(str(language), iso_code)


# pylint: disable=no-member
class LocaleTests(TestCase):
    """ Language model tests. """

    def test_str(self):
        iso_code = "en-US"
        language = Language(iso_code=iso_code)
        self.assertEqual(str(language), iso_code)


# pylint: disable=no-member
class CurrencyTests(TestCase):
    """ Language model tests. """

    def test_str(self):
        iso_code = "USD"
        language = Language(iso_code=iso_code)
        self.assertEqual(str(language), iso_code)
