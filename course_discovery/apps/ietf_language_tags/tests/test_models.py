""" Tests for ietf language tag models. """

from django.test import TestCase

from course_discovery.apps.ietf_language_tags.models import LanguageTag


class LanguageTagTests(TestCase):
    """ Tests for the LanguageTag class. """

    def test_str(self):
        """ Verify LanguageTag returns a string containing the ID and name of the model. """

        lcid = 'te-st',
        name = 'Test LanguageTag'
        langtag = LanguageTag(id=lcid, name=name)
        self.assertEqual(str(langtag), '{lcid} - {name}'.format(lcid=lcid, name=name))
