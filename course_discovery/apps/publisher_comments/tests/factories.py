import factory
from django.contrib.sites.models import Site

from course_discovery.apps.core.tests.factories import UserFactory
from course_discovery.apps.publisher.tests.factories import CourseRunFactory
from course_discovery.apps.publisher_comments.models import Comments


class SiteFactory(factory.DjangoModelFactory):  # pylint: disable=missing-docstring
    class Meta(object):  # pylint: disable=missing-docstring
        model = Site


class CommentFactory(factory.DjangoModelFactory):

    comment = factory.fuzzy.FuzzyText(prefix="Test Comment for çօմɾʂҽ")
    content_object = factory.SubFactory(CourseRunFactory)
    user = factory.SubFactory(UserFactory)
    site = factory.SubFactory(SiteFactory)

    class Meta:
        model = Comments
