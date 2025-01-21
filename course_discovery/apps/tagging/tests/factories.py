""" Factories for tagging app models """
import factory
from factory.django import DjangoModelFactory
from factory.fuzzy import FuzzyText

from course_discovery.apps.course_metadata.tests.factories import CourseFactory
from course_discovery.apps.tagging.models import CourseVertical, SubVertical, UpdateCourseVerticalsConfig, Vertical


class VerticalFactory(DjangoModelFactory):
    """
    Factory for Vertical model
    """
    class Meta:
        model = Vertical

    name = FuzzyText()
    is_active = True


class SubVerticalFactory(DjangoModelFactory):
    """
    Factory for SubVertical model
    """
    class Meta:
        model = SubVertical

    name = FuzzyText()
    vertical = factory.SubFactory(VerticalFactory)
    is_active = True


class CourseVerticalFactory(DjangoModelFactory):
    """
    Factory for CourseVertical model
    """
    class Meta:
        model = CourseVertical

    course = factory.SubFactory(CourseFactory)
    vertical = factory.SubFactory(VerticalFactory)
    sub_vertical = factory.SubFactory(SubVerticalFactory)


class UpdateCourseVerticalsConfigFactory(DjangoModelFactory):
    """
    Factory for UpdateCourseVerticalsConfig model
    """
    class Meta:
        model = UpdateCourseVerticalsConfig
