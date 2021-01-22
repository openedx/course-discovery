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

    def test_translated_macrolanguage(self):
        """ Verify the property returns the translated macrolanguage for a given LanguageTag. """
        en_us = LanguageTag(code='en-us', name='English - United States')
        en_us.name_t = 'Inglés - Estados Unidos'
        self.assertEqual(en_us.translated_macrolanguage, 'Inglés')

    def test_search_facet_display_untranslated(self):
        en_us = LanguageTag(code='en_US', name='English - United States')
        zh_cn = LanguageTag(code='zh_CN', name='Chinese - Traditional')
        en_us.set_current_language('es')
        zh_cn.set_current_language('es')
        en_us.name_t = 'Inglés - Estados Unidos'
        zh_cn.name_t = 'Chino - Tradicional'
        self.assertEqual(en_us.get_search_facet_display(), 'English')
        self.assertEqual(zh_cn.get_search_facet_display(), 'Chinese - Traditional')

    def test_search_facet_display_translated(self):
        en_us = LanguageTag(code='en_US', name='English - United States')
        zh_cn = LanguageTag(code='zh_CN', name='Chinese - Traditional')
        en_us.set_current_language('es')
        zh_cn.set_current_language('es')
        zh_cn.name_t = 'Chino - Tradicional'
        en_us.name_t = 'Inglés - Estados Unidos'
        self.assertEqual(en_us.get_search_facet_display(translate=True), 'Inglés')
        self.assertEqual(zh_cn.get_search_facet_display(translate=True), 'Chino - Tradicional')
