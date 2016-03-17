import factory
from factory.fuzzy import FuzzyText

from course_discovery.apps.course_metadata.models import Course


class CourseFactory(factory.Factory):
    class Meta(object):
        model = Course
        exclude = ('name',)

    id = FuzzyText(prefix='course-id/', suffix='/fake')
    name = FuzzyText(prefix="էҽʂէ çօմɾʂҽ ")

    @factory.lazy_attribute
    def body(self):
        return {
            'id': self.id,
            'name': self.name
        }

    @classmethod
    def _create(cls, model_class, *args, **kwargs):
        obj = model_class(*args, **kwargs)
        obj.save()
        return obj
