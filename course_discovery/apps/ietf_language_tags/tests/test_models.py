""" Tests for models. """

from django.test import TestCase

from course_discovery.apps.ietf_language_tags.models import LanguageTag


class LanguageTagTests(TestCase):
    """ Tests for the LanguageTag class. """

    def test_str(self):
        """ Verify casting a LanguageTag to a string returns a string containing the code and name of the model. """

        code = 'te-st',
        name = 'Test LanguageTag'
        tag = LanguageTag(code=code, name=name)
        self.assertEqual(str(tag), tag.name)

    def test_macrolanguage(self):
        """ Verify the property returns the macrolanguage for a given LanguageTag. """
        en_us = LanguageTag(code='en-us', name='English - United States')
        self.assertEqual(en_us.macrolanguage, 'English')

        sw = LanguageTag(code='sw', name='Swahili')
        self.assertEqual(sw.macrolanguage, 'Swahili')
