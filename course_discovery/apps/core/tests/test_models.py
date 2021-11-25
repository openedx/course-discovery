""" Tests for core models. """
import ddt
from pytest import mark
from django.test import TestCase

from course_discovery.apps.core.models import Currency
from course_discovery.apps.core.tests.factories import PartnerFactory, UserFactory

@mark.django_db
class UserTests(TestCase):
    """ User model tests. """

    def setUp(self):
        super().setUp()
        self.user = UserFactory()

    def test_get_full_name(self):
        """ Test that the user model concatenates first and last name if the full name is not set. """
        full_name = "George Costanza"
        user = UserFactory(full_name=full_name)
        assert user.get_full_name() == full_name

        first_name = "Jerry"
        last_name = "Seinfeld"
        user = UserFactory(full_name=None, first_name=first_name, last_name=last_name)
        expected = f"{first_name} {last_name}"
        assert user.get_full_name() == expected

        user = UserFactory(full_name=full_name, first_name=first_name, last_name=last_name)
        assert user.get_full_name() == full_name


class CurrencyTests(TestCase):
    """ Tests for the Currency class. """

    def test_str(self):
        """ Verify casting an instance to a string returns a string containing the ID and name of the currency. """

        code = 'USD'
        name = 'U.S. Dollar'
        instance = Currency(code=code, name=name)
        assert str(instance) == f'{code} - {name}'


@ddt.ddt
class PartnerTests(TestCase):
    """ Tests for the Partner class. """

    def test_str(self):
        """ Verify the method returns the name of the Partner. """

        partner = PartnerFactory()
        assert str(partner) == partner.name

    @ddt.unpack
    @ddt.data(
        ('', False),
        (None, False),
        ('https://example.com', True),
    )
    def test_has_marketing_site(self, marketing_site_url_root, expected):
        partner = PartnerFactory(marketing_site_url_root=marketing_site_url_root)
        assert partner.has_marketing_site == expected
