import json

from haystack import indexes
from opaque_keys.edx.keys import CourseKey

from course_discovery.apps.course_metadata.models import Course, CourseRun, Program


class OrganizationsMixin:
    def format_organization(self, organization):
        return '{key}: {name}'.format(key=organization.key, name=organization.name)

    def format_organization_body(self, organization):
        # Deferred to prevent a circular import:
        # course_discovery.apps.api.serializers -> course_discovery.apps.course_metadata.search_indexes
        from course_discovery.apps.api.serializers import OrganizationSerializer

        return json.dumps(OrganizationSerializer(organization).data)

    def _prepare_organizations(self, organizations):
        return [self.format_organization(organization) for organization in organizations]

    def prepare_authoring_organizations(self, obj):
        return self._prepare_organizations(obj.authoring_organizations.all())


class BaseIndex(indexes.SearchIndex):
    model = None

    text = indexes.CharField(document=True, use_template=True)
    content_type = indexes.CharField(faceted=True)

    def prepare_content_type(self, obj):  # pylint: disable=unused-argument
        return self.model.__name__.lower()

    def get_model(self):
        return self.model

    def get_updated_field(self):  # pragma: no cover
        return 'modified'

    def index_queryset(self, using=None):
        return self.model.objects.all()


class BaseCourseIndex(OrganizationsMixin, BaseIndex):
    key = indexes.CharField(model_attr='key', stored=True)
    title = indexes.CharField(model_attr='title')
    short_description = indexes.CharField(model_attr='short_description', null=True)
    full_description = indexes.CharField(model_attr='full_description', null=True)
    subjects = indexes.MultiValueField(faceted=True)
    organizations = indexes.MultiValueField(faceted=True)
    authoring_organizations = indexes.MultiValueField(faceted=True)
    sponsoring_organizations = indexes.MultiValueField(faceted=True)
    level_type = indexes.CharField(null=True, faceted=True)
    partner = indexes.CharField(model_attr='partner__short_code', null=True, faceted=True)

    def prepare_subjects(self, obj):
        return [subject.name for subject in obj.subjects.all()]

    def prepare_organizations(self, obj):
        return self.prepare_authoring_organizations(obj) + self.prepare_sponsoring_organizations(obj)

    def prepare_authoring_organizations(self, obj):
        return self._prepare_organizations(obj.authoring_organizations.all())

    def prepare_sponsoring_organizations(self, obj):
        return self._prepare_organizations(obj.sponsoring_organizations.all())

    def prepare_level_type(self, obj):
        return obj.level_type.name if obj.level_type else None


class CourseIndex(BaseCourseIndex, indexes.Indexable):
    model = Course

    course_runs = indexes.MultiValueField()
    expected_learning_items = indexes.MultiValueField()

    prerequisites = indexes.MultiValueField(faceted=True)

    def prepare_course_runs(self, obj):
        return [course_run.key for course_run in obj.course_runs.all()]

    def prepare_expected_learning_items(self, obj):
        return [item.value for item in obj.expected_learning_items.all()]

    def prepare_prerequisites(self, obj):
        return [prerequisite.name for prerequisite in obj.prerequisites.all()]


class CourseRunIndex(BaseCourseIndex, indexes.Indexable):
    model = CourseRun

    course_key = indexes.CharField(model_attr='course__key', stored=True)
    org = indexes.CharField()
    number = indexes.CharField()
    start = indexes.DateTimeField(model_attr='start', null=True, faceted=True)
    end = indexes.DateTimeField(model_attr='end', null=True)
    enrollment_start = indexes.DateTimeField(model_attr='enrollment_start', null=True)
    enrollment_end = indexes.DateTimeField(model_attr='enrollment_end', null=True)
    announcement = indexes.DateTimeField(model_attr='announcement', null=True)
    min_effort = indexes.IntegerField(model_attr='min_effort', null=True)
    max_effort = indexes.IntegerField(model_attr='max_effort', null=True)
    language = indexes.CharField(null=True, faceted=True)
    transcript_languages = indexes.MultiValueField(faceted=True)
    pacing_type = indexes.CharField(model_attr='pacing_type', null=True, faceted=True)
    marketing_url = indexes.CharField(null=True)
    slug = indexes.CharField(model_attr='slug', null=True)
    seat_types = indexes.MultiValueField(model_attr='seat_types', null=True, faceted=True)
    type = indexes.CharField(model_attr='type', null=True, faceted=True)
    image_url = indexes.CharField(model_attr='card_image_url', null=True)
    partner = indexes.CharField(model_attr='course__partner__short_code', null=True, faceted=True)

    def _prepare_language(self, language):
        return language.macrolanguage

    def prepare_language(self, obj):
        if obj.language:
            return self._prepare_language(obj.language)
        return None

    def prepare_number(self, obj):
        course_run_key = CourseKey.from_string(obj.key)
        return course_run_key.course

    def prepare_org(self, obj):
        course_run_key = CourseKey.from_string(obj.key)
        return course_run_key.org

    def prepare_transcript_languages(self, obj):
        return [self._prepare_language(language) for language in obj.transcript_languages.all()]

    def prepare_marketing_url(self, obj):
        return obj.marketing_url


class ProgramIndex(BaseIndex, indexes.Indexable, OrganizationsMixin):
    model = Program

    uuid = indexes.CharField(model_attr='uuid')
    title = indexes.CharField(model_attr='title')
    subtitle = indexes.CharField(model_attr='subtitle')
    type = indexes.CharField(model_attr='type__name', faceted=True)
    marketing_url = indexes.CharField(null=True)
    organizations = indexes.MultiValueField(faceted=True)
    authoring_organizations = indexes.MultiValueField(faceted=True)
    authoring_organization_bodies = indexes.MultiValueField()
    credit_backing_organizations = indexes.MultiValueField(faceted=True)
    card_image_url = indexes.CharField(model_attr='card_image_url', null=True)
    status = indexes.CharField(model_attr='status', faceted=True)
    partner = indexes.CharField(model_attr='partner__short_code', null=True, faceted=True)
    start = indexes.DateTimeField(model_attr='start', null=True, faceted=True)
    seat_types = indexes.MultiValueField(model_attr='seat_types', null=True, faceted=True)

    def prepare_organizations(self, obj):
        return self.prepare_authoring_organizations(obj) + self.prepare_credit_backing_organizations(obj)

    def prepare_authoring_organization_bodies(self, obj):
        return [self.format_organization_body(organization) for organization in obj.authoring_organizations.all()]

    def prepare_credit_backing_organizations(self, obj):
        return self._prepare_organizations(obj.credit_backing_organizations.all())

    def prepare_marketing_url(self, obj):
        return obj.marketing_url
