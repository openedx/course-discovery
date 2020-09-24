""" IETF language tag models. """

from django.db import models
from django.utils.translation import ugettext_lazy as _
from parler.models import TranslatableModel, TranslatedFieldsModel


class LanguageTag(TranslatableModel):
    """ Table of language tags as defined by BCP 47. https://tools.ietf.org/html/bcp47 """
    code = models.CharField(max_length=50, primary_key=True)
    name = models.CharField(max_length=255)

    def __str__(self):
        return self.name

    @property
    def macrolanguage(self):
        return self.name.split('-')[0].strip()

    @property
    def translated_macrolanguage(self):
        return self.name_t.split('-')[0].strip()

    def get_search_facet_display(self, translate=False):
        # Only Chinese languages (Chinese - Mandarin, Chinese - Traditional, etc.) are separate facets for search.
        # All other languages are grouped by macrolanguage.
        if self.code.startswith('zh'):
            return self.name_t if translate else self.name
        return self.translated_macrolanguage if translate else self.macrolanguage


class LanguageTagTranslation(TranslatedFieldsModel):
    master = models.ForeignKey(LanguageTag, models.CASCADE, related_name='translations', null=True)
    name_t = models.CharField(_('Name for translation'), max_length=255)

    class Meta:
        unique_together = ('language_code', 'master')
        verbose_name = _('LanguageTag model translations')
