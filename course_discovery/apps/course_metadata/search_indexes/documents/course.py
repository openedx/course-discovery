from django.conf import settings
from django_elasticsearch_dsl import fields, Index
from opaque_keys.edx.keys import CourseKey

from course_discovery.apps.course_metadata.models import Course
from .analyzers import html_strip
from .common import BaseCourseDocument, filter_visible_runs

__all__ = ('CourseDocument',)

COURSE_INDEX = Index(settings.ELASTICSEARCH_INDEX_NAMES[__name__])
COURSE_INDEX.settings(
    number_of_shards=1,
    number_of_replicas=0,
    blocks={'read_only_allow_delete': None},
)


@COURSE_INDEX.doc_type
class CourseDocument(BaseCourseDocument):
    """
    Course Elasticsearch document.
    """

    uuid = fields.KeywordField()
    card_image_url = fields.TextField()
    image_url = fields.TextField()
    org = fields.KeywordField()
    modified = fields.DateField()
    first_enrollable_paid_seat_price = fields.IntegerField()
    subject_uuids = fields.KeywordField(multi=True)
    course_runs = fields.KeywordField(multi=True)
    expected_learning_items = fields.KeywordField(multi=True)
    partner = fields.TextField(analyzer=html_strip, fields={'raw': fields.KeywordField()})
    prerequisites = fields.KeywordField(multi=True)
    languages = fields.KeywordField(multi=True)
    seat_types = fields.KeywordField(multi=True)

    def get_queryset(self):
        # TODO: Build queryset smartly.
        return super().get_queryset().prefetch_related('course_runs__seats__type')

    def prepare_partner(self, obj):
        return obj.partner.short_code

    def prepare_aggregation_key(self, obj):
        return 'course:{}'.format(obj.key)

    def prepare_course_runs(self, obj):
        return [course_run.key for course_run in filter_visible_runs(obj.course_runs)]

    def prepare_expected_learning_items(self, obj):
        return [item.value for item in obj.expected_learning_items.all()]

    def prepare_prerequisites(self, obj):
        return [prerequisite.name for prerequisite in obj.prerequisites.all()]

    def prepare_org(self, obj):
        course_run = filter_visible_runs(obj.course_runs).first()
        if course_run:
            return CourseKey.from_string(course_run.key).org
        return None

    def prepare_first_enrollable_paid_seat_price(self, obj):
        return obj.first_enrollable_paid_seat_price

    def prepare_seat_types(self, obj):
        seat_types = [seat.slug for run in filter_visible_runs(obj.course_runs) for seat in run.seat_types]
        return list(set(seat_types))

    def prepare_subject_uuids(self, obj):
        return [str(subject.uuid) for subject in obj.subjects.all()]

    def prepare_languages(self, obj):
        return list(
            {
                self._prepare_language(course_run.language)
                for course_run in filter_visible_runs(obj.course_runs)
                if course_run.language
            }
        )

    class Django:
        """
        Django Elasticsearch DSL ORM Meta.
        """

        model = Course

    class Meta:
        """
        Meta options.
        """

        parallel_indexing = True
        queryset_pagination = 50
