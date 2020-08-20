from django.conf import settings
from django_elasticsearch_dsl import Index, fields

from course_discovery.apps.course_metadata.models import Person, Position

from .common import BaseDocument
from .analyzers import html_strip
__all__ = ('PersonDocument',)

PERSON_INDEX_NAME = settings.ELASTICSEARCH_INDEX_NAMES[__name__]
PERSON_INDEX = Index(PERSON_INDEX_NAME)
PERSON_INDEX.settings(number_of_shards=1, number_of_replicas=1, blocks={'read_only_allow_delete': None})


@PERSON_INDEX.doc_type
class PersonDocument(BaseDocument):
    """
    Person Elasticsearch document.
    """

    bio = fields.TextField()
    bio_language = fields.TextField()
    full_name = fields.TextField()
    get_profile_image_url = fields.TextField()
    organizations = fields.KeywordField(multi=True)
    position = fields.TextField(multi=True)

    def prepare_aggregation_key(self, obj):
        return 'person:{}'.format(obj.uuid)

    def prepare_bio_language(self, obj):
        if obj.bio_language:
            return obj.bio_language.name
        return None

    def prepare_organizations(self, obj):
        course_runs = obj.courses_staffed.all()
        all_organizations = [course_run.course.authoring_organizations.all() for course_run in course_runs]
        formatted_organizations = [org.key for orgs in all_organizations for org in orgs]
        return formatted_organizations

    def prepare_position(self, obj):
        try:
            position = Position.objects.get(person=obj)
        except Position.DoesNotExist:
            return []
        return [position.title, position.organization_override]

    def get_queryset(self):
        return super().get_queryset().select_related('bio_language')

    class Django:

        """
        Django Elasticsearch DSL ORM Meta.
        """
        model = Person

    class Meta:

        """
        Meta options.
        """
        parallel_indexing = True
        queryset_pagination = settings.ELASTICSEARCH_DSL_QUERYSET_PAGINATION
