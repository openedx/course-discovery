import json

from haystack import indexes
from opaque_keys.edx.keys import CourseKey

from course_discovery.apps.course_metadata.choices import CourseRunStatus, ProgramStatus
from course_discovery.apps.course_metadata.models import Course, CourseRun, Degree, Person, Position, Program

BASE_SEARCH_INDEX_FIELDS = (
    'aggregation_key',
    'content_type',
    'text',
)

BASE_PROGRAM_FIELDS = (
    'card_image_url',
    'language',
    'marketing_url',
    'partner',
    'published',
    'status',
    'subtitle',
    'text',
    'title',
    'type',
    'uuid'
)

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


def filter_visible_runs(course_runs):
    return course_runs.exclude(type__is_marketable=False)


class OrganizationsMixin:
    def format_organization(self, organization):
        return '{key}: {name}'.format(key=organization.key, name=organization.name)

    def format_organization_body(self, organization):
        # Deferred to prevent a circular import:
        # course_discovery.apps.api.serializers -> course_discovery.apps.course_metadata.search_indexes
        from course_discovery.apps.api.serializers import OrganizationSerializer  # pylint: disable=import-outside-toplevel

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
            return language.get_search_facet_display()
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
    outcome = indexes.CharField(model_attr='outcome', null=True)
    partner = indexes.CharField(model_attr='partner__short_code', null=True, faceted=True)

    def prepare_logo_image_urls(self, obj):
        orgs = obj.authoring_organizations.all()
        return [org.logo_image.url for org in orgs if org.logo_image]

    def prepare_subjects(self, obj):
        return [subject.name for subject in obj.subjects.all()]

    def prepare_organizations(self, obj):
        return set(self.prepare_authoring_organizations(obj) + self.prepare_sponsoring_organizations(obj))

    def prepare_authoring_organizations(self, obj):
        return self._prepare_organizations(obj.authoring_organizations.all())

    def prepare_sponsoring_organizations(self, obj):
        return self._prepare_organizations(obj.sponsoring_organizations.all())

    def prepare_level_type(self, obj):
        return obj.level_type.name if obj.level_type else None


class CourseIndex(BaseCourseIndex, indexes.Indexable):
    model = Course

    uuid = indexes.CharField(model_attr='uuid')
    card_image_url = indexes.CharField(model_attr='card_image_url', null=True)
    image_url = indexes.CharField(model_attr='image_url', null=True)
    org = indexes.CharField()

    status = indexes.CharField(model_attr='course_runs__status')
    start = indexes.DateTimeField(model_attr='course_runs__start', null=True)
    end = indexes.DateTimeField(model_attr='course_runs__end', null=True)
    modified = indexes.DateTimeField(model_attr='modified', null=True)
    enrollment_start = indexes.DateTimeField(model_attr='course_runs__enrollment_start', null=True)
    enrollment_end = indexes.DateTimeField(model_attr='course_runs__enrollment_end', null=True)
    availability = indexes.CharField(model_attr='course_runs__availability')
    first_enrollable_paid_seat_price = indexes.IntegerField(null=True)
    subject_uuids = indexes.MultiValueField()

    course_runs = indexes.MultiValueField()
    expected_learning_items = indexes.MultiValueField()

    prerequisites = indexes.MultiValueField(faceted=True)
    languages = indexes.MultiValueField()
    seat_types = indexes.MultiValueField()

    def read_queryset(self, using=None):
        # Pre-fetch all fields required by the CourseSearchSerializer. Unfortunately, there's
        # no way to specify at query time which queryset to use during loading in order to customize
        # it for the serializer being used
        qset = super(CourseIndex, self).read_queryset(using=using)
        return qset.prefetch_related(
            'course_runs__seats__type'
        )

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
        return {
            self._prepare_language(course_run.language) for course_run in filter_visible_runs(obj.course_runs)
            if course_run.language
        }


class CourseRunIndex(BaseCourseIndex, indexes.Indexable):
    model = CourseRun

    course_key = indexes.CharField(model_attr='course__key', stored=True)
    org = indexes.CharField()
    number = indexes.CharField()
    status = indexes.CharField(model_attr='status', faceted=True)
    start = indexes.DateTimeField(model_attr='start', null=True, faceted=True)
    end = indexes.DateTimeField(model_attr='end', null=True)
    go_live_date = indexes.DateTimeField(model_attr='go_live_date', null=True)
    enrollment_start = indexes.DateTimeField(model_attr='enrollment_start', null=True)
    enrollment_end = indexes.DateTimeField(model_attr='enrollment_end', null=True)
    availability = indexes.CharField(model_attr='availability')
    announcement = indexes.DateTimeField(model_attr='announcement', null=True)
    min_effort = indexes.IntegerField(model_attr='min_effort', null=True)
    max_effort = indexes.IntegerField(model_attr='max_effort', null=True)
    weeks_to_complete = indexes.IntegerField(model_attr='weeks_to_complete', null=True)
    language = indexes.CharField(null=True, faceted=True)
    transcript_languages = indexes.MultiValueField(faceted=True)
    pacing_type = indexes.CharField(model_attr='pacing_type', null=True, faceted=True)
    marketing_url = indexes.CharField(null=True)
    slug = indexes.CharField(model_attr='slug', null=True)
    seat_types = indexes.MultiValueField(model_attr='seat_types__slug', null=True, faceted=True)
    type = indexes.CharField(model_attr='type_legacy', null=True, faceted=True)
    image_url = indexes.CharField(model_attr='image_url', null=True)
    partner = indexes.CharField(null=True, faceted=True)
    program_types = indexes.MultiValueField()
    published = indexes.BooleanField(null=False, faceted=True)
    hidden = indexes.BooleanField(model_attr='hidden', faceted=True)
    mobile_available = indexes.BooleanField(model_attr='mobile_available', faceted=True)
    authoring_organization_uuids = indexes.MultiValueField()
    staff_uuids = indexes.MultiValueField()
    subject_uuids = indexes.MultiValueField()
    has_enrollable_paid_seats = indexes.BooleanField(null=False)
    first_enrollable_paid_seat_sku = indexes.CharField(null=True)
    first_enrollable_paid_seat_price = indexes.IntegerField(null=True)
    paid_seat_enrollment_end = indexes.DateTimeField(null=True)
    license = indexes.MultiValueField(model_attr='license', faceted=True)
    has_enrollable_seats = indexes.BooleanField(model_attr='has_enrollable_seats', null=False)
    is_current_and_still_upgradeable = indexes.BooleanField(null=False)

    def read_queryset(self, using=None):
        # Pre-fetch all fields required by the CourseRunSearchSerializer. Unfortunately, there's
        # no way to specify at query time which queryset to use during loading in order to customize
        # it for the serializer being used
        qset = super(CourseRunIndex, self).read_queryset(using=using)

        return qset.prefetch_related(
            'seats__type',
        )

    def index_queryset(self, using=None):
        return filter_visible_runs(super().index_queryset(using=using))

    def prepare_aggregation_key(self, obj):
        # Aggregate CourseRuns by Course key since that is how we plan to dedup CourseRuns on the marketing site.
        return 'courserun:{}'.format(obj.course.key)

    def prepare_has_enrollable_paid_seats(self, obj):
        return obj.has_enrollable_paid_seats()

    def prepare_first_enrollable_paid_seat_sku(self, obj):
        return obj.first_enrollable_paid_seat_sku()

    def prepare_first_enrollable_paid_seat_price(self, obj):
        return obj.first_enrollable_paid_seat_price

    def prepare_is_current_and_still_upgradeable(self, obj):
        return obj.is_current_and_still_upgradeable()

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
    type = indexes.CharField(model_attr='type__name_t', faceted=True)
    marketing_url = indexes.CharField(null=True)
    search_card_display = indexes.MultiValueField()
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
    seat_types = indexes.MultiValueField(model_attr='seat_types__slug', null=True, faceted=True)
    published = indexes.BooleanField(null=False, faceted=True)
    min_hours_effort_per_week = indexes.IntegerField(model_attr='min_hours_effort_per_week', null=True)
    max_hours_effort_per_week = indexes.IntegerField(model_attr='max_hours_effort_per_week', null=True)
    weeks_to_complete_min = indexes.IntegerField(model_attr='weeks_to_complete_min', null=True)
    weeks_to_complete_max = indexes.IntegerField(model_attr='weeks_to_complete_max', null=True)
    language = indexes.MultiValueField(faceted=True)
    hidden = indexes.BooleanField(model_attr='hidden', faceted=True)
    is_program_eligible_for_one_click_purchase = indexes.BooleanField(
        model_attr='is_program_eligible_for_one_click_purchase', null=False
    )

    def prepare_aggregation_key(self, obj):
        return 'program:{}'.format(obj.uuid)

    def prepare_published(self, obj):
        return obj.status == ProgramStatus.Active

    def prepare_organizations(self, obj):
        return self.prepare_authoring_organizations(obj) + self.prepare_credit_backing_organizations(obj)

    def prepare_subject_uuids(self, obj):
        return [str(subject.uuid) for subject in obj.subjects]

    def prepare_staff_uuids(self, obj):
        return {str(staff.uuid) for course_run in obj.course_runs for staff in course_run.staff.all()}

    def prepare_credit_backing_organizations(self, obj):
        return self._prepare_organizations(obj.credit_backing_organizations.all())

    def prepare_marketing_url(self, obj):
        return obj.marketing_url

    def prepare_language(self, obj):
        return [self._prepare_language(language) for language in obj.languages]

    def prepare_search_card_display(self, obj):
        try:
            degree = Degree.objects.get(uuid=obj.uuid)
        except Degree.DoesNotExist:

            return []
        return [degree.search_card_ranking, degree.search_card_cost, degree.search_card_courses]


class PersonIndex(BaseIndex, indexes.Indexable):
    model = Person
    uuid = indexes.CharField(model_attr='uuid')
    salutation = indexes.CharField(model_attr='salutation', null=True)
    full_name = indexes.CharField(model_attr='full_name')
    partner = indexes.CharField(null=True)
    bio = indexes.CharField(model_attr='bio', null=True)
    bio_language = indexes.CharField(model_attr='bio_language', null=True)
    get_profile_image_url = indexes.CharField(model_attr='get_profile_image_url', null=True)
    position = indexes.MultiValueField()
    organizations = indexes.MultiValueField(faceted=True)

    def prepare_aggregation_key(self, obj):
        return 'person:{}'.format(obj.uuid)

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

    def prepare_bio_language(self, obj):
        if obj.bio_language:
            return obj.bio_language.name
        return None
