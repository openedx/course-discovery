import re

from django import forms
from django.core.validators import RegexValidator
from django.db import models
from django.utils.translation import gettext_lazy as _
from django_extensions.db.fields import AutoSlugField

from course_discovery.apps.course_metadata.validators import validate_html


class HtmlField(models.TextField):
    def __init__(self, **kwargs):
        validators = set(kwargs.pop('validators', []))
        validators.add(validate_html)
        super().__init__(validators=validators, **kwargs)


class NullHtmlField(HtmlField):
    def __init__(self, **kwargs):
        kwargs.setdefault('blank', True)
        kwargs.setdefault('default', None)
        kwargs.setdefault('null', True)
        super().__init__(**kwargs)


SLUG_ALLOWED_CHARS = re.compile(r'^[-a-zA-Z0-9_/]+\Z')


validate_slug_with_slashes = RegexValidator(
    SLUG_ALLOWED_CHARS,
    # Translators: "letters" means latin letters: a-z and A-Z.
    _("Enter a valid “slug” consisting of letters, numbers, slashes, underscores or hyphens."),
    "invalid",
)


class SlashSlugField(forms.SlugField):
    """ Custom SlugField to allow slashes in the slug. """
    default_validators = [validate_slug_with_slashes]


class AutoSlugWithSlashesField(AutoSlugField):
    """ Custom AutoSlugField to allow slashes in the slug. """
    default_validators = [validate_slug_with_slashes]

    def formfield(self, **kwargs):
        return super().formfield(
            **{
                "form_class": SlashSlugField,
                "allow_unicode": self.allow_unicode,
                **kwargs,
            }
        )
