from django.conf import settings
from django_elasticsearch_dsl import Index, fields
from opaque_keys.edx.keys import CourseKey

from course_discovery.apps.course_metadata.choices import CourseRunStatus
from course_discovery.apps.course_metadata.models import CourseRun

from .analyzers import case_insensitive_keyword, html_strip
from .common import BaseCourseDocument, filter_visible_runs

__all__ = ('CourseRunDocument',)

COURSE_RUN_INDEX_NAME = settings.ELASTICSEARCH_INDEX_NAMES[__name__]
COURSE_RUN_INDEX = Index(COURSE_RUN_INDEX_NAME)
COURSE_RUN_INDEX.settings(
    number_of_shards=1,
    number_of_replicas=1,
    blocks={'read_only_allow_delete': None},
)


@COURSE_RUN_INDEX.doc_type
class CourseRunDocument(BaseCourseDocument):
    """
    Course run Elasticsearch document.
    """

    announcement = fields.DateField()
    availability = fields.TextField(
        fields={'raw': fields.KeywordField(), 'lower': fields.TextField(analyzer=case_insensitive_keyword)}
    )
    authoring_organization_uuids = fields.KeywordField(multi=True)
    course_key = fields.KeywordField()
    end = fields.DateField()
    enrollment_start = fields.DateField()
    enrollment_end = fields.DateField()
    first_enrollable_paid_seat_sku = fields.TextField()
    go_live_date = fields.DateField()
    has_enrollable_seats = fields.BooleanField()
    has_enrollable_paid_seats = fields.BooleanField()
    hidden = fields.BooleanField()
    is_enrollable = fields.BooleanField()
    is_current_and_still_upgradeable = fields.BooleanField()
    language = fields.TextField(
        analyzer=html_strip, fields={'raw': fields.KeywordField()}
    )
    license = fields.KeywordField()
    marketing_url = fields.TextField()
    min_effort = fields.IntegerField()
    max_effort = fields.IntegerField()
    mobile_available = fields.BooleanField()
    number = fields.KeywordField()
    paid_seat_enrollment_end = fields.DateField()
    pacing_type = fields.KeywordField()
    program_types = fields.KeywordField(multi=True)
    published = fields.BooleanField()
    status = fields.KeywordField()
    start = fields.DateField()
    slug = fields.TextField()
    staff_uuids = fields.KeywordField(multi=True)
    type = fields.KeywordField(attr='type_legacy')
    transcript_languages = fields.TextField(
        analyzer=html_strip, fields={'raw': fields.KeywordField(multi=True)}, multi=True
    )
    weeks_to_complete = fields.IntegerField()

    def prepare_aggregation_key(self, obj):
        # Aggregate CourseRuns by Course key since that is how we plan to dedup CourseRuns on the marketing site.
        return 'courserun:{}'.format(obj.course.key)

    def prepare_course_key(self, obj):
        return obj.course.key

    def prepare_first_enrollable_paid_seat_sku(self, obj):
        return obj.first_enrollable_paid_seat_sku()

    def prepare_is_current_and_still_upgradeable(self, obj):
        return obj.is_current_and_still_upgradeable()

    def prepare_has_enrollable_paid_seats(self, obj):
        return obj.has_enrollable_paid_seats()

    def prepare_language(self, obj):
        return self._prepare_language(obj.language)

    def prepare_number(self, obj):
        course_run_key = CourseKey.from_string(obj.key)
        return course_run_key.course

    def prepare_org(self, obj):
        course_run_key = CourseKey.from_string(obj.key)
        return course_run_key.org

    def prepare_paid_seat_enrollment_end(self, obj):
        return obj.get_paid_seat_enrollment_end()

    def prepare_partner(self, obj):
        return obj.course.partner.short_code

    def prepare_published(self, obj):
        return obj.status == CourseRunStatus.Published

    def prepare_seat_types(self, obj):
        return [seat_type.slug for seat_type in obj.seat_types]

    def prepare_staff_uuids(self, obj):
        return [str(staff.uuid) for staff in obj.staff.all()]

    def prepare_transcript_languages(self, obj):
        return [
            self._prepare_language(language)
            for language in obj.transcript_languages.all()
        ]

    def get_queryset(self):
        return filter_visible_runs(
            super().get_queryset()
                   .select_related('course')
                   .prefetch_related('seats__type')
                   .prefetch_related('transcript_languages')
        )

    class Django:
        """
        Django Elasticsearch DSL ORM Meta.
        """

        model = CourseRun

    class Meta:
        """
        Meta options.
        """

        parallel_indexing = True
        queryset_pagination = settings.ELASTICSEARCH_DSL_QUERYSET_PAGINATION
