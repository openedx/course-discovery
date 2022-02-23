from django.conf import settings
from django_elasticsearch_dsl import Index, fields

from course_discovery.apps.learner_pathway.choices import PathwayStatus
from course_discovery.apps.learner_pathway.models import LearnerPathway

from .analyzers import case_insensitive_keyword, edge_ngram_completion, html_strip, synonym_text
from .common import BaseDocument, OrganizationsMixin

__all__ = ('LearnerPathwayDocument',)

LEARNER_PATHWAY_INDEX_NAME = settings.ELASTICSEARCH_INDEX_NAMES[__name__]
LEARNER_PATHWAY_INDEX = Index(LEARNER_PATHWAY_INDEX_NAME)
LEARNER_PATHWAY_INDEX.settings(number_of_shards=1, number_of_replicas=1, blocks={'read_only_allow_delete': None})


@LEARNER_PATHWAY_INDEX.doc_type
class LearnerPathwayDocument(BaseDocument, OrganizationsMixin):
    """
    LearnerPathway Elasticsearch document.
    """

    name = fields.TextField(
        analyzer=synonym_text,
        fields={
            'suggest': fields.CompletionField(),
            'edge_ngram_completion': fields.TextField(analyzer=edge_ngram_completion),
        },
    )
    partner = fields.TextField(
        analyzer=html_strip,
        fields={'raw': fields.KeywordField(), 'lower': fields.TextField(analyzer=case_insensitive_keyword)}
    )
    visible_via_association = fields.BooleanField()
    status = fields.TextField()
    overview = fields.TextField()
    published = fields.BooleanField()
    skill_names = fields.KeywordField(multi=True)
    skills = fields.NestedField(properties={
        'name': fields.TextField(),
        'description': fields.TextField(),
    })

    def prepare_aggregation_key(self, obj):
        return 'learnerpathway:{}'.format(obj.uuid)

    def prepare_partner(self, obj):
        return obj.partner.short_code

    def prepare_published(self, obj):
        return obj.status == PathwayStatus.Active

    def get_queryset(self):
        return super().get_queryset().prefetch_related(
            'steps', 'steps__learnerpathwaycourse_set', 'steps__learnerpathwayprogram_set',
            'steps__learnerpathwayblock_set'
        )

    def prepare_skill_names(self, obj):
        return [skill['name'] for skill in obj.skills]

    def prepare_skills(self, obj):
        return obj.skills

    class Django:
        """
        Django Elasticsearch DSL ORM Meta.
        """

        model = LearnerPathway

    class Meta:
        """
        Meta options.
        """

        parallel_indexing = True
        queryset_pagination = settings.ELASTICSEARCH_DSL_QUERYSET_PAGINATION
