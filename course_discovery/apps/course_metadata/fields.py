from django.db import models

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
