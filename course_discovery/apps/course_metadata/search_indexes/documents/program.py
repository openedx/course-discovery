from django.conf import settings
from django_elasticsearch_dsl import Index, fields

from course_discovery.apps.course_metadata.choices import ProgramStatus
from course_discovery.apps.course_metadata.models import Degree, Program

from .analyzers import case_insensitive_keyword, edge_ngram_completion, html_strip, synonym_text
from .common import BaseDocument, OrganizationsMixin

__all__ = ('ProgramDocument',)

PROGRAM_INDEX_NAME = settings.ELASTICSEARCH_INDEX_NAMES[__name__]
PROGRAM_INDEX = Index(PROGRAM_INDEX_NAME)
PROGRAM_INDEX.settings(number_of_shards=1, number_of_replicas=1, blocks={'read_only_allow_delete': None})


@PROGRAM_INDEX.doc_type
class ProgramDocument(BaseDocument, OrganizationsMixin):
    """
    Program Elasticsearch document.
    """

    authoring_organization_uuids = fields.KeywordField(multi=True)
    authoring_organizations = fields.TextField(
        multi=True,
        fields={
            'suggest': fields.CompletionField(),
            'edge_ngram_completion': fields.TextField(analyzer=edge_ngram_completion),
            'raw': fields.KeywordField(),
            'lower': fields.TextField(analyzer=case_insensitive_keyword)
        },
    )
    authoring_organization_bodies = fields.TextField(multi=True)
    credit_backing_organizations = fields.TextField(multi=True)
    card_image_url = fields.TextField()
    hidden = fields.BooleanField()
    is_program_eligible_for_one_click_purchase = fields.BooleanField()
    language = fields.TextField(multi=True)
    marketing_url = fields.TextField()
    min_hours_effort_per_week = fields.IntegerField()
    max_hours_effort_per_week = fields.IntegerField()
    partner = fields.TextField(
        analyzer=html_strip,
        fields={'raw': fields.KeywordField(), 'lower': fields.TextField(analyzer=case_insensitive_keyword)}
    )
    published = fields.BooleanField()
    subtitle = fields.TextField(analyzer=html_strip)
    status = fields.KeywordField()
    search_card_display = fields.TextField(multi=True)
    subject_uuids = fields.KeywordField(multi=True)
    staff_uuids = fields.KeywordField(multi=True)
    start = fields.DateField()
    seat_types = fields.KeywordField(multi=True)
    title = fields.TextField(
        analyzer=synonym_text,
        fields={
            'suggest': fields.CompletionField(),
            'edge_ngram_completion': fields.TextField(analyzer=edge_ngram_completion),
        },
    )
    type = fields.TextField(
        analyzer=html_strip,
        fields={'raw': fields.KeywordField(), 'lower': fields.TextField(analyzer=case_insensitive_keyword)}
    )
    weeks_to_complete_min = fields.IntegerField()
    weeks_to_complete_max = fields.IntegerField()
    is_2u_degree_program = fields.BooleanField()

    def prepare_aggregation_key(self, obj):
        return 'program:{}'.format(obj.uuid)

    def prepare_credit_backing_organizations(self, obj):
        return self._prepare_organizations(obj.credit_backing_organizations.all())

    def prepare_language(self, obj):
        return [self._prepare_language(language) for language in obj.languages]

    def prepare_organizations(self, obj):
        return self.prepare_authoring_organizations(obj) + self.prepare_credit_backing_organizations(obj)

    def prepare_partner(self, obj):
        return obj.partner.short_code

    def prepare_published(self, obj):
        return obj.status == ProgramStatus.Active

    def prepare_seat_types(self, obj):
        return [seat_type.slug for seat_type in obj.seat_types]

    def prepare_search_card_display(self, obj):
        try:
            degree = Degree.objects.get(uuid=obj.uuid)
        except Degree.DoesNotExist:

            return []
        return [degree.search_card_ranking, degree.search_card_cost, degree.search_card_courses]

    def prepare_subject_uuids(self, obj):
        return [str(subject.uuid) for subject in obj.subjects]

    def prepare_staff_uuids(self, obj):
        return list({str(staff.uuid) for course_run in obj.course_runs for staff in course_run.staff.all()})

    def prepare_type(self, obj):
        return obj.type.name_t

    def get_queryset(self):
        return super().get_queryset().select_related('type').select_related('partner')

    class Django:
        """
        Django Elasticsearch DSL ORM Meta.
        """

        model = Program

    class Meta:
        """
        Meta options.
        """

        parallel_indexing = True
        queryset_pagination = settings.ELASTICSEARCH_DSL_QUERYSET_PAGINATION
