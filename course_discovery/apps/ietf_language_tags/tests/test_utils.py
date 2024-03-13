""" Tests for the ietf_language_tags utility methods """

import ddt
import pytest
from django.test import TestCase

from course_discovery.apps.ietf_language_tags.models import LanguageTag
from course_discovery.apps.ietf_language_tags.utils import serialize_language


@ddt.ddt
@pytest.mark.django_db
class SerializeLanguageTest(TestCase):
    """
    Tests for serialize_language method
    """

    def setUp(self):
        super().setUp()
        self.language_1 = LanguageTag.objects.filter(code__startswith='zh').first()
        self.language_2 = LanguageTag.objects.filter(code__startswith='en').first()

    def test_serialize_language__with_language(self):
        """
        Test that serialize_language method returns the language name
        if the language code starts with 'zh' else returns the macrolanguage.
        """
        assert serialize_language(self.language_1) == self.language_1.name
        assert serialize_language(self.language_2) == self.language_2.macrolanguage
