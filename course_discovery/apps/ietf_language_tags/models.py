""" IETF language tag models. """

from django.db import models


class LanguageTag(models.Model):
    """ Table of language tags as defined by BCP 47. https://tools.ietf.org/html/bcp47 """
    code = models.CharField(max_length=50, primary_key=True)
    name = models.CharField(max_length=255)

    def __str__(self):
        return self.name

    @property
    def macrolanguage(self):
        return self.name.split('-')[0].strip()
