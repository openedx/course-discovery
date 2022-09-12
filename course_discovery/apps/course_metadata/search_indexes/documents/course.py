from django.conf import settings
from django_elasticsearch_dsl import Index, fields
from opaque_keys.edx.keys import CourseKey
from taxonomy.utils import get_whitelisted_course_skills, get_whitelisted_serialized_skills

from course_discovery.apps.course_metadata.models import Course

from .analyzers import case_insensitive_keyword
from .common import BaseCourseDocument, filter_visible_runs

__all__ = ('CourseDocument',)

COURSE_INDEX_NAME = settings.ELASTICSEARCH_INDEX_NAMES[__name__]
COURSE_INDEX = Index(COURSE_INDEX_NAME)
COURSE_INDEX.settings(
    number_of_shards=1,
    number_of_replicas=1,
    blocks={'read_only_allow_delete': None},
)


@COURSE_INDEX.doc_type
class CourseDocument(BaseCourseDocument):
    """
    Course Elasticsearch document.
    """

    availability = fields.TextField(
        fields={'raw': fields.KeywordField(), 'lower': fields.TextField(analyzer=case_insensitive_keyword)},
        multi=True
    )
    card_image_url = fields.TextField()
    course_runs = fields.KeywordField(multi=True)
    expected_learning_items = fields.KeywordField(multi=True)
    end = fields.DateField(multi=True)
    course_ends = fields.TextField(
        fields={'raw': fields.KeywordField(), 'lower': fields.TextField(analyzer=case_insensitive_keyword)}
    )
    end_date = fields.DateField()
    enrollment_start = fields.DateField(multi=True)
    enrollment_end = fields.DateField(multi=True)
    first_enrollable_paid_seat_price = fields.IntegerField()
    languages = fields.KeywordField(multi=True)
    modified = fields.DateField()
    prerequisites = fields.KeywordField(multi=True)
    skill_names = fields.KeywordField(multi=True)
    skills = fields.NestedField(properties={
        'name': fields.TextField(),
        'description': fields.TextField(),
    })
    status = fields.KeywordField(multi=True)
    start = fields.DateField(multi=True)
    course_type = fields.KeywordField(multi=True)
    enterprise_subscription_inclusion = fields.BooleanField()

    def prepare_aggregation_key(self, obj):
        return 'course:{}'.format(obj.key)

    def prepare_availability(self, obj):
        return [str(course_run.availability) for course_run in filter_visible_runs(obj.course_runs)]

    def prepare_course_runs(self, obj):
        return [course_run.key for course_run in filter_visible_runs(obj.course_runs)]

    def prepare_expected_learning_items(self, obj):
        return [item.value for item in obj.expected_learning_items.all()]

    def prepare_languages(self, obj):
        return list(
            {
                self._prepare_language(course_run.language)
                for course_run in filter_visible_runs(obj.course_runs)
                if course_run.language
            }
        )

    def prepare_end(self, obj):
        return [course_run.end for course_run in filter_visible_runs(obj.course_runs)]

    def prepare_end_date(self, obj):
        return obj.end_date

    def prepare_course_ends(self, obj):
        return str(obj.course_ends)

    def prepare_enrollment_start(self, obj):
        return [course_run.enrollment_start for course_run in filter_visible_runs(obj.course_runs)]

    def prepare_enrollment_end(self, obj):
        return [course_run.enrollment_end for course_run in filter_visible_runs(obj.course_runs)]

    def prepare_org(self, obj):
        course_run = filter_visible_runs(obj.course_runs).first()
        if course_run:
            return CourseKey.from_string(course_run.key).org
        return None

    def prepare_seat_types(self, obj):
        seat_types = [seat.slug for run in filter_visible_runs(obj.course_runs) for seat in run.seat_types]
        return list(set(seat_types))

    def prepare_skill_names(self, obj):
        course_skills = get_whitelisted_course_skills(obj.key)
        return list(set(course_skill.skill.name for course_skill in course_skills))

    def prepare_skills(self, obj):
        return get_whitelisted_serialized_skills(obj.key)

    def prepare_status(self, obj):
        return [course_run.status for course_run in filter_visible_runs(obj.course_runs)]

    def prepare_start(self, obj):
        return [course_run.start for course_run in filter_visible_runs(obj.course_runs)]

    def prepare_partner(self, obj):
        return obj.partner.short_code

    def prepare_prerequisites(self, obj):
        return [prerequisite.name for prerequisite in obj.prerequisites.all()]

    def get_queryset(self):
        return super().get_queryset().prefetch_related('course_runs__seats__type')

    def prepare_course_type(self, obj):
        return obj.type.slug

    def prepare_enterprise_subscription_inclusion(self, obj):
        return obj.enterprise_subscription_inclusion

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
        queryset_pagination = settings.ELASTICSEARCH_DSL_QUERYSET_PAGINATION
