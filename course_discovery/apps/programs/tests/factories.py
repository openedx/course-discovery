"""
Factories for tests of Programs.
"""

from django.utils.crypto import get_random_string
import factory

from course_discovery.apps.course_metadata.tests.factories import OrganizationFactory
from course_discovery.apps.programs import models
from course_discovery.apps.programs.constants import ProgramCategory, ProgramStatus

# pylint: disable=missing-docstring,unnecessary-lambda


class CourseRequirementFactory(factory.django.DjangoModelFactory):
    class Meta(object):
        model = models.CourseRequirement

    id = factory.Sequence(lambda n: n)
    key = factory.LazyAttribute(lambda o: get_random_string(3).upper())
    display_name = factory.LazyAttribute(lambda o: '{} Course'.format(o.key))
    organization = factory.SubFactory(OrganizationFactory)


class ProgramFactory(factory.django.DjangoModelFactory):
    class Meta(object):
        model = models.Program

    name = factory.Sequence(lambda n: 'test-program-{}'.format(n))
    external_id = 1
    subtitle = "test-subtitle"
    category = ProgramCategory.XSERIES
    status = ProgramStatus.UNPUBLISHED
    marketing_slug = factory.Sequence(lambda n: 'test-slug-{}'.format(n))


class ProgramOrganizationFactory(factory.django.DjangoModelFactory):
    class Meta(object):
        model = models.ProgramOrganization


class ProgramCourseRequirementFactory(factory.django.DjangoModelFactory):
    class Meta(object):
        model = models.ProgramCourseRequirement

    id = factory.Sequence(lambda n: n)
