""" IETF language tag models. """

from django.db import models


class LanguageTag(models.Model):
    """ Table of language tags as defined by BCP 47. https://tools.ietf.org/html/bcp47 """
    id = models.CharField(max_length=50, primary_key=True)
    name = models.CharField(max_length=255)

    def __str__(self):
        return '{id} - {name}'.format(id=self.id, name=self.name)
