"""
Model factory classes for testing.
"""

import factory

from course_discovery.apps.taxonomy_support.models import SkillValidationConfiguration


class SkillValidationConfigurationFactory(factory.django.DjangoModelFactory):

    class Meta:
        model = SkillValidationConfiguration
