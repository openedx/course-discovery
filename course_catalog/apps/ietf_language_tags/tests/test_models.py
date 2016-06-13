""" Tests for models. """

from django.test import TestCase

from course_catalog.apps.ietf_language_tags.models import LanguageTag


class LanguageTagTests(TestCase):
    """ Tests for the LanguageTag class. """

    def test_str(self):
        """ Verify casting a LanguageTag to a string returns a string containing the code and name of the model. """

        code = 'te-st',
        name = 'Test LanguageTag'
        tag = LanguageTag(code=code, name=name)
        self.assertEqual(str(tag), '{code} - {name}'.format(code=code, name=name))
