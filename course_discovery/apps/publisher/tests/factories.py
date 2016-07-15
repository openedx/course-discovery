import factory
from factory.fuzzy import FuzzyText, FuzzyChoice


from course_discovery.apps.course_metadata.tests.factories import CourseRunFactory
from course_discovery.apps.publisher.models import Status, CourseRunDetail
from course_discovery.apps.core.tests.factories import UserFactory


class StatusFactory(factory.DjangoModelFactory):
    name = FuzzyChoice([name for name, __ in Status.STATUS_CHOICES])
    course_run = factory.SubFactory(CourseRunFactory)
    updated_by = factory.SubFactory(UserFactory)

    class Meta:
        model = Status


class CourseRunDetailFactory(factory.DjangoModelFactory):
    course_run = factory.SubFactory(CourseRunFactory)
    is_re_run = FuzzyChoice((True, False,))
    program_type = FuzzyChoice([name for name, __ in CourseRunDetail.PROGRAMS_CHOICES])
    program_name = FuzzyText()
    seo_review = "test-seo-review"
    keywords = 'Test1, Test2, Test3'
    notes = 'Testing notes'
    certificate_generation_exception = 'Generate certificate on demand'
    course_length = FuzzyChoice((1, 2, 3, 4, 5,))
    target_content = FuzzyChoice((True, False,))
    priority = FuzzyChoice((True, False,))

    class Meta:
        model = CourseRunDetail
