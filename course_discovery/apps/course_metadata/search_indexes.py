import json

from haystack import indexes
from opaque_keys.edx.keys import CourseKey

from course_discovery.apps.course_metadata.choices import CourseRunStatus, ProgramStatus
from course_discovery.apps.course_metadata.models import Course, CourseRun, Program

# http://django-haystack.readthedocs.io/en/v2.5.0/boost.html#field-boost
# Boost title over all other parameters (multiplicative)
# The max boost received from our boosting functions is ~6.
# Having a boost of 25 for title gives most relevant titles a score higher
# than our other boosting (which is what we want). But it's all relative.
# If we altered our boosting functions to have a max score of 10
# we would probably want to bump this number.
TITLE_FIELD_BOOST = 25.0
# We want to boost org the same as title
# Primarily this is to prevent courses from other institutions
# coming up first if there is a partial match on title
ORG_FIELD_BOOST = TITLE_FIELD_BOOST


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

    def prepare_authoring_organization_bodies(self, obj):
        return [self.format_organization_body(organization) for organization in obj.authoring_organizations.all()]

    def prepare_authoring_organizations(self, obj):
        return self._prepare_organizations(obj.authoring_organizations.all())

    def prepare_authoring_organizations_autocomplete(self, obj):
        return self.prepare_authoring_organizations(obj)


class BaseIndex(indexes.SearchIndex):
    model = None

    # A key that can be used to group related documents together to enable the computation of distinct facet and hit
    # counts.
    aggregation_key = indexes.CharField()
    content_type = indexes.CharField(faceted=True)
    text = indexes.CharField(document=True, use_template=True)

    def prepare_content_type(self, obj):  # pylint: disable=unused-argument
        return self.model.__name__.lower()

    def get_model(self):
        return self.model

    def get_updated_field(self):  # pragma: no cover
        return 'modified'

    def index_queryset(self, using=None):
        return self.model.objects.all()

    def prepare_authoring_organization_uuids(self, obj):
        return [str(organization.uuid) for organization in obj.authoring_organizations.all()]

    def _prepare_language(self, language):
        if language:
            # ECOM-5466: Render the macro language for all languages except Chinese
            if language.code.startswith('zh'):
                return language.name
            else:
                return language.macrolanguage

        return None


class BaseCourseIndex(OrganizationsMixin, BaseIndex):
    key = indexes.CharField(model_attr='key', stored=True)
    title = indexes.CharField(model_attr='title', boost=TITLE_FIELD_BOOST)
    title_autocomplete = indexes.NgramField(model_attr='title', boost=TITLE_FIELD_BOOST)
    authoring_organizations_autocomplete = indexes.NgramField(boost=ORG_FIELD_BOOST)
    authoring_organization_bodies = indexes.MultiValueField()
    short_description = indexes.CharField(model_attr='short_description', null=True)
    full_description = indexes.CharField(model_attr='full_description', null=True)
    subjects = indexes.MultiValueField(faceted=True)
    organizations = indexes.MultiValueField(faceted=True)
    authoring_organizations = indexes.MultiValueField(faceted=True)
    logo_image_urls = indexes.MultiValueField()
    sponsoring_organizations = indexes.MultiValueField(faceted=True)
    level_type = indexes.CharField(null=True, faceted=True)
    partner = indexes.CharField(model_attr='partner__short_code', null=True, faceted=True)

    def prepare_logo_image_urls(self, obj):
        orgs = obj.authoring_organizations.all()
        return [org.logo_image_url for org in orgs]

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

    def prepare_aggregation_key(self, obj):
        return 'course:{}'.format(obj.key)

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
    status = indexes.CharField(model_attr='status', faceted=True)
    start = indexes.DateTimeField(model_attr='start', null=True, faceted=True)
    end = indexes.DateTimeField(model_attr='end', null=True)
    enrollment_start = indexes.DateTimeField(model_attr='enrollment_start', null=True)
    enrollment_end = indexes.DateTimeField(model_attr='enrollment_end', null=True)
    announcement = indexes.DateTimeField(model_attr='announcement', null=True)
    min_effort = indexes.IntegerField(model_attr='min_effort', null=True)
    max_effort = indexes.IntegerField(model_attr='max_effort', null=True)
    weeks_to_complete = indexes.IntegerField(model_attr='weeks_to_complete', null=True)
    language = indexes.CharField(null=True, faceted=True)
    transcript_languages = indexes.MultiValueField(faceted=True)
    pacing_type = indexes.CharField(model_attr='pacing_type', null=True, faceted=True)
    marketing_url = indexes.CharField(null=True)
    slug = indexes.CharField(model_attr='slug', null=True)
    seat_types = indexes.MultiValueField(model_attr='seat_types', null=True, faceted=True)
    type = indexes.CharField(model_attr='type', null=True, faceted=True)
    image_url = indexes.CharField(model_attr='card_image_url', null=True)
    partner = indexes.CharField(null=True, faceted=True)
    program_types = indexes.MultiValueField()
    published = indexes.BooleanField(null=False, faceted=True)
    hidden = indexes.BooleanField(model_attr='hidden', faceted=True)
    mobile_available = indexes.BooleanField(model_attr='mobile_available', faceted=True)
    authoring_organization_uuids = indexes.MultiValueField()
    staff_uuids = indexes.MultiValueField()
    subject_uuids = indexes.MultiValueField()
    has_enrollable_paid_seats = indexes.BooleanField(null=False)
    paid_seat_enrollment_end = indexes.DateTimeField(null=True)

    def prepare_aggregation_key(self, obj):
        # Aggregate CourseRuns by Course key since that is how we plan to dedup CourseRuns on the marketing site.
        return 'courserun:{}'.format(obj.course.key)

    def prepare_has_enrollable_paid_seats(self, obj):
        return obj.has_enrollable_paid_seats()

    def prepare_paid_seat_enrollment_end(self, obj):
        return obj.get_paid_seat_enrollment_end()

    def prepare_partner(self, obj):
        return obj.course.partner.short_code

    def prepare_published(self, obj):
        return obj.status == CourseRunStatus.Published

    def prepare_language(self, obj):
        return self._prepare_language(obj.language)

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

    def prepare_program_types(self, obj):
        return obj.program_types

    def prepare_staff_uuids(self, obj):
        return [str(staff.uuid) for staff in obj.staff.all()]

    def prepare_subject_uuids(self, obj):
        return [str(subject.uuid) for subject in obj.subjects.all()]


class ProgramIndex(BaseIndex, indexes.Indexable, OrganizationsMixin):
    model = Program

    uuid = indexes.CharField(model_attr='uuid')
    title = indexes.CharField(model_attr='title', boost=TITLE_FIELD_BOOST)
    title_autocomplete = indexes.NgramField(model_attr='title', boost=TITLE_FIELD_BOOST)
    subtitle = indexes.CharField(model_attr='subtitle')
    type = indexes.CharField(model_attr='type__name', faceted=True)
    marketing_url = indexes.CharField(null=True)
    organizations = indexes.MultiValueField(faceted=True)
    authoring_organizations = indexes.MultiValueField(faceted=True)
    authoring_organizations_autocomplete = indexes.NgramField(boost=ORG_FIELD_BOOST)
    authoring_organization_uuids = indexes.MultiValueField()
    subject_uuids = indexes.MultiValueField()
    staff_uuids = indexes.MultiValueField()
    authoring_organization_bodies = indexes.MultiValueField()
    credit_backing_organizations = indexes.MultiValueField(faceted=True)
    card_image_url = indexes.CharField(model_attr='card_image_url', null=True)
    status = indexes.CharField(model_attr='status', faceted=True)
    partner = indexes.CharField(model_attr='partner__short_code', null=True, faceted=True)
    start = indexes.DateTimeField(model_attr='start', null=True, faceted=True)
    seat_types = indexes.MultiValueField(model_attr='seat_types', null=True, faceted=True)
    published = indexes.BooleanField(null=False, faceted=True)
    min_hours_effort_per_week = indexes.IntegerField(model_attr='min_hours_effort_per_week', null=True)
    max_hours_effort_per_week = indexes.IntegerField(model_attr='max_hours_effort_per_week', null=True)
    weeks_to_complete_min = indexes.IntegerField(model_attr='weeks_to_complete_min', null=True)
    weeks_to_complete_max = indexes.IntegerField(model_attr='weeks_to_complete_max', null=True)
    language = indexes.MultiValueField(faceted=True)
    hidden = indexes.BooleanField(model_attr='hidden', faceted=True)

    def prepare_aggregation_key(self, obj):
        return 'program:{}'.format(obj.uuid)

    def prepare_published(self, obj):
        return obj.status == ProgramStatus.Active

    def prepare_organizations(self, obj):
        return self.prepare_authoring_organizations(obj) + self.prepare_credit_backing_organizations(obj)

    def prepare_subject_uuids(self, obj):
        return [str(subject.uuid) for course in obj.courses.all() for subject in course.subjects.all()]

    def prepare_staff_uuids(self, obj):
        return [str(staff.uuid) for course_run in obj.course_runs for staff in course_run.staff.all()]

    def prepare_credit_backing_organizations(self, obj):
        return self._prepare_organizations(obj.credit_backing_organizations.all())

    def prepare_marketing_url(self, obj):
        return obj.marketing_url

    def prepare_language(self, obj):
        return [self._prepare_language(language) for language in obj.languages]
