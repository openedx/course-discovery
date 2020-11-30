import json
from fnmatch import fnmatch

from django.core.exceptions import ObjectDoesNotExist
from django.template import loader
from django.template.exceptions import TemplateDoesNotExist
from django_elasticsearch_dsl import Document as OriginDocument
from django_elasticsearch_dsl import fields

from course_discovery.apps.edx_elasticsearch_dsl_extensions.search import Search

from .analyzers import case_insensitive_keyword, edge_ngram_completion, html_strip, synonym_text


def filter_visible_runs(course_runs):
    """
    Filter course runs objects so only objects of type `is_marketable` are displayed
    """
    return course_runs.exclude(type__is_marketable=False)


class OrganizationsMixin:
    """
    OrganizationsMixin to be able prepare a set specific fields for es index.
    """

    def format_organization(self, organization):
        return '{key}: {name}'.format(key=organization.key, name=organization.name)

    def format_organization_body(self, organization):
        # NOTE: Deferred to prevent a circular import:
        # course_discovery.apps.api.serializers -> course_discovery.apps.course_metadata.search_indexes
        # pylint: disable=import-outside-toplevel
        from course_discovery.apps.api.serializers import OrganizationSerializer

        return json.dumps(OrganizationSerializer(organization).data)

    def _prepare_organizations(self, organizations):
        return [self.format_organization(organization) for organization in organizations]

    def prepare_authoring_organization_bodies(self, obj):
        return [self.format_organization_body(organization) for organization in obj.authoring_organizations.all()]

    def prepare_authoring_organizations(self, obj):
        return self._prepare_organizations(obj.authoring_organizations.all())

    def prepare_authoring_organizations_autocomplete(self, obj):
        return self.prepare_authoring_organizations(obj)


class Document(OriginDocument):
    """
    Extended Document class.

    Implements:
        - addition of accelerators(boosting) as `funtion_scopes`
        query for each search request to Elasticsearch.

        https://www.elastic.co/guide/en/elasticsearch/reference/current/query-dsl-function-score-query.html,

        - default search pagination.
    """

    @classmethod
    def search(cls, using=None, index=None):
        """
        Constructor of elasticsearch dls `Search` class.

        Creates custom `Search` class instance that will search
        over this `Document`.
        Custom `Search` is child class of main elasticsearch dls original `Search`.
        """
        return Search(
            using=cls._get_using(using),
            index=cls._default_index(index),
            doc_type=[cls]
        )


class DocumentMeta(Document.__class__):
    """
    Meta class, which extends the capabilities of Document metaclass.

    Dynamically adds shared attributes to indexes where there are no such attributes.
    This is necessary for an aggregated search, i.e. search in all indices at the same time,
    since the sort must go through the field that all indices have.
    Otherwise, Elasticsearch will return an exception with error code 400.
    """

    def __new__(mcs, name, parents, attrs):
        def prepare_start(self, obj):  # pylint: disable=unused-argument
            return None

        if not name.startswith('Base') and 'start' not in attrs:
            attrs['start'] = fields.DateField()
            attrs[prepare_start.__name__] = prepare_start

        return super().__new__(mcs, name, parents, attrs)


class BaseDocument(Document, metaclass=DocumentMeta):
    """
    Base document index.

    Contains common fields for all indexes.
    It implements some features that were in the django-haystack library,
    and the absence of which in django-elasticsearch-dsl breaks the existing business logic.
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._object = None

    aggregation_key = fields.KeywordField()
    content_type = fields.KeywordField()
    id = fields.KeywordField()
    organizations = fields.TextField(analyzer=html_strip, multi=True, fields={'raw': fields.KeywordField(multi=True)})
    pk = fields.IntegerField()
    text = fields.TextField(analyzer=synonym_text)
    uuid = fields.KeywordField()

    def get_queryset(self):
        return self.django.model.objects.all()

    @classmethod
    def _matches(cls, hit):
        # pylint: disable=protected-access
        if cls._index._name is None:
            return True
        return fnmatch(hit.get('_index', ''), '{}*'.format(cls._index._name))

    def _get_object(self):
        if self._object is None:
            try:
                self._object = self.get_queryset().get(pk=self.pk)
            except ObjectDoesNotExist:
                self._object = None

        return self._object

    def _set_object(self, obj):
        self._object = obj

    def _prepare_language(self, language):
        if language:
            return language.get_search_facet_display()
        return None

    object = property(_get_object, _set_object)

    def prepare_authoring_organization_uuids(self, obj):
        return [str(organization.uuid) for organization in obj.authoring_organizations.all()]

    def prepare_content_type(self, obj):  # pylint: disable=unused-argument
        return self.Django.model.__name__.lower()

    def prepare_id(self, obj):
        return '{0}.{1}.{2}'.format(obj._meta.app_label, obj._meta.model_name, obj.pk)

    def prepare_text(self, obj):
        """
        Flattens an object for indexing.

        This loads a template
        (``search/indexes/{app_label}/{model_name}.txt``) and
        returns the result of rendering that template. ``object`` will be in
        its context.
        """
        template_names = ['search/indexes/%s/%s_text.txt' % (obj._meta.app_label, obj._meta.model_name)]
        try:
            t = loader.select_template(template_names)
        except TemplateDoesNotExist:
            return ''
        return t.render({'object': obj})


class BaseCourseDocument(OrganizationsMixin, BaseDocument):
    """
    Base course document index.

    Contains common fields and logic for Course and CourseRun indexes.
    """
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
    key = fields.KeywordField()
    title = fields.TextField(
        analyzer=synonym_text,
        fields={
            'suggest': fields.CompletionField(),
            'edge_ngram_completion': fields.TextField(analyzer=edge_ngram_completion),
        },
    )
    first_enrollable_paid_seat_price = fields.IntegerField()
    full_description = fields.TextField(analyzer=html_strip)
    image_url = fields.TextField()
    logo_image_urls = fields.TextField(multi=True)
    level_type = fields.TextField(
        fields={'raw': fields.KeywordField(), 'lower': fields.TextField(analyzer=case_insensitive_keyword)}
    )
    partner = fields.TextField(
        analyzer=html_strip,
        fields={'raw': fields.KeywordField(), 'lower': fields.TextField(analyzer=case_insensitive_keyword)}
    )
    outcome = fields.TextField()
    org = fields.TextField(
        analyzer=html_strip,
        fields={'raw': fields.KeywordField(), 'lower': fields.TextField(analyzer=case_insensitive_keyword)}
    )
    subject_uuids = fields.KeywordField(multi=True)
    short_description = fields.TextField(analyzer=html_strip)
    seat_types = fields.KeywordField(multi=True)
    subjects = fields.TextField(analyzer=html_strip, fields={'raw': fields.KeywordField(multi=True)}, multi=True)
    sponsoring_organizations = fields.TextField(multi=True)

    def prepare_first_enrollable_paid_seat_price(self, obj):
        return obj.first_enrollable_paid_seat_price

    def prepare_level_type(self, obj):
        return obj.level_type.name if obj.level_type else None

    def prepare_logo_image_urls(self, obj):
        orgs = obj.authoring_organizations.all()
        return [org.logo_image.url for org in orgs if org.logo_image]

    def prepare_organizations(self, obj):
        return list(set(self.prepare_authoring_organizations(obj) + self.prepare_sponsoring_organizations(obj)))

    def prepare_subjects(self, obj):
        return [subject.name for subject in obj.subjects.all()]

    def prepare_subject_uuids(self, obj):
        return [str(subject.uuid) for subject in obj.subjects.all()]

    def prepare_sponsoring_organizations(self, obj):
        return self._prepare_organizations(obj.sponsoring_organizations.all())
