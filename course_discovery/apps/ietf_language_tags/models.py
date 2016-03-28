""" IETF Language Tag models. """

from django.db import models


class Locale(models.Model):
    """ Table of locales as defined by BCP 47. """
    id = models.CharField(max_length=50, primary_key=True, unique=True)
    name = models.CharField(max_length=255)
    language_code = models.CharField(max_length=3)

    def __str__(self):
        return '{id} - {name}'.format(id=self.id, name=self.name)
