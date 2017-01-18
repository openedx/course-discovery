from django.utils.translation import ugettext_lazy as _
from jsonfield.fields import JSONField
from solo.models import SingletonModel


class ElasticsearchBoostConfig(SingletonModel):
    """
    Model used to store the elasticsearch boost configuration.
    This includes a default JSON config for the function_score.
    """

    # The primary key used to save the solo record to the DB.
    # This is hardcoded to 1 in https://github.com/lazybird/django-solo/blob/1.1.2/solo/models.py
    # but may be configurable in later releases.
    SINGLETON_INSTANCE_PRIMARY_KEY = 1

    function_score = JSONField(
        verbose_name=_('Function Score'),
        help_text=_('JSON string containing an elasticsearch function score config.'),
        null=False,
        blank=False,
        default={
            'functions': [],
            'boost': 1.0,
            'score_mode': 'multiply',
            'boost_mode': 'multiply'
        }
    )
