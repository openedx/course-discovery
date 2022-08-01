import datetime
import itertools

import pytz
from django.db import models
from django.utils.translation import gettext as _
from django.utils.translation import override
from sortedm2m.fields import SortedManyToManyField

from course_discovery.apps.course_metadata.choices import CourseRunStatus, ProgramStatus
from course_discovery.apps.course_metadata.models import (
    AbstractLocationRestrictionModel, Course, CourseType, Program, ProgramType
)

# Algolia can't filter on an empty list, provide a value we can still filter on
EMPTY_LOCATION_RESTRICTION_LIST = ['null']


# Utility methods used by both courses and programs
def get_active_language_tag(course):
    if course.advertised_course_run and course.advertised_course_run.language:
        return course.advertised_course_run.language
    return None


def get_active_language(course):
    if get_active_language_tag(course):
        return get_active_language_tag(course).get_search_facet_display(translate=True)
    return None


def logo_image(owner):
    image = getattr(owner, 'logo_image', None)
    if image:
        return image.url
    return None


def get_owners(entry):
    all_owners = [{'key': o.key, 'logoImageUrl': logo_image(o), 'name': o.name}
                  for o in entry.authoring_organizations.all()]
    return list(filter(lambda owner: owner['logoImageUrl'] is not None, all_owners))


def delegate_attributes(cls):
    '''
    Class decorator. For all Algolia fields, when my_instance.attribute is accessed, get the attribute off
    my_instance.product rather than my_instance. This allows us to combine two different models into one index. If
    my_instance.product doesn't have the attribute, attempts to access it will just return None.

    This doesn't work as well for field names that exist on the underlying Course and Program models so those
    fields are prefixed with 'product_' to make them Algolia-specific
    '''

    product_type_fields = ['product_type']
    search_fields = ['partner_names', 'partner_keys', 'product_title', 'primary_description', 'secondary_description',
                     'tertiary_description']
    facet_fields = ['availability_level', 'subject_names', 'levels', 'active_languages', 'staff_slugs',
                    'product_allowed_in', 'product_blocked_in']
    ranking_fields = ['availability_rank', 'product_recent_enrollment_count', 'promoted_in_spanish_index']
    result_fields = ['product_marketing_url', 'product_card_image_url', 'product_uuid', 'product_weeks_to_complete',
                     'product_max_effort', 'product_min_effort', 'active_run_key', 'active_run_start',
                     'active_run_type', 'owners', 'program_types', 'course_titles', 'tags',
                     'product_organization_short_code_override', 'product_organization_logo_override']
    object_id_field = ['custom_object_id', ]
    fields = product_type_fields + search_fields + facet_fields + ranking_fields + result_fields + object_id_field
    for field in fields:
        def _closure(name):
            def _wrap(self, *args, **kwargs):
                with override(getattr(self.product, 'language', 'en')):
                    return getattr(self.product, name, None)
            return _wrap
        setattr(cls, field, _closure(field))
    return cls


def get_course_availability(course):
    all_runs = course.course_runs.filter(status=CourseRunStatus.Published)
    availability = set()

    for course_run in all_runs:
        if course_run.is_current():
            availability.add(_('Available now'))
        elif course_run.is_upcoming():
            availability.add(_('Upcoming'))
        else:
            availability.add(_('Archived'))

    return list(availability)

# Proxies Program model in order to trick Algolia into thinking this is a single model so it doesn't error.
# No model-specific attributes or methods are actually used.


def get_location_restriction(location_restriction):
    if (len(location_restriction.countries) == 0 and len(location_restriction.states) == 0):
        return EMPTY_LOCATION_RESTRICTION_LIST

    # Combine list of country and state codes in order to make filtering in Algolia easier
    states = ['US-' + state for state in location_restriction.states]
    return location_restriction.countries + states


@delegate_attributes
class AlgoliaProxyProduct(Program):
    class Meta:
        proxy = True

    def __init__(self, product, language='en'):
        super().__init__()
        self.product = product
        self.product.language = language

    # should_index is called differently from algoliasearch_django, can't use the delegate_attributes trick
    def should_index(self):
        return getattr(self.product, 'should_index', True)

    def should_index_spanish(self):
        return getattr(self.product, 'should_index_spanish', True)


class AlgoliaBasicModelFieldsMixin(models.Model):

    class Meta:
        abstract = True

    @property
    def product_title(self):
        return self.title

    @property
    def product_uuid(self):
        return self.uuid

    @property
    def product_marketing_url(self):
        return self.marketing_url

    @property
    def product_recent_enrollment_count(self):
        return self.recent_enrollment_count


class AlgoliaProxyCourse(Course, AlgoliaBasicModelFieldsMixin):

    class Meta:
        proxy = True

    @property
    def product_type(self):
        if self.type.slug == CourseType.EXECUTIVE_EDUCATION_2U:
            return 'Executive Education'
        if self.type.slug == CourseType.BOOTCAMP_2U:
            return 'Boot Camp'
        return 'Course'

    @property
    def custom_object_id(self):
        return f'course-{self.uuid}'

    @property
    def primary_description(self):
        return self.short_description

    @property
    def secondary_description(self):
        return self.outcome

    @property
    def tertiary_description(self):
        return self.full_description

    @property
    def active_languages(self):
        language = get_active_language(self)
        if language:
            return [language]
        return None

    @property
    def active_run_key(self):
        return getattr(self.advertised_course_run, 'key', None)

    @property
    def active_run_start(self):
        return getattr(self.advertised_course_run, 'start', None)

    @property
    def active_run_type(self):
        return getattr(self.advertised_course_run, 'type', None)

    @property
    def availability_level(self):
        return get_course_availability(self)

    @property
    def partner_names(self):
        return [org['name'] for org in get_owners(self)]

    @property
    def partner_keys(self):
        return [org['key'] for org in get_owners(self)]

    @property
    def levels(self):
        level = getattr(self.level_type, 'name_t', None)
        if level:
            return [level]
        return None

    @property
    def subject_names(self):
        return [subject.name for subject in self.subjects.all()]

    @property
    def program_types(self):
        return [program.type.name for program in self.programs.all()]

    @property
    def product_card_image_url(self):
        if self.image:
            return getattr(self.image, 'url', None)
        return None

    @property
    def product_weeks_to_complete(self):
        return getattr(self.advertised_course_run, 'weeks_to_complete', None)

    @property
    def product_min_effort(self):
        return getattr(self.advertised_course_run, 'min_effort', None)

    @property
    def product_max_effort(self):
        return getattr(self.advertised_course_run, 'max_effort', None)

    @property
    def product_organization_short_code_override(self):
        return self.organization_short_code_override

    @property
    def product_organization_logo_override(self):
        if self.organization_logo_override:
            return getattr(self.organization_logo_override, 'url', None)
        return None

    @property
    def owners(self):
        return get_owners(self)

    @property
    def staff_slugs(self):
        staff = [course_run.staff.all() for course_run in self.active_course_runs]
        staff = itertools.chain.from_iterable(staff)
        return list({person.slug for person in staff})

    @property
    def promoted_in_spanish_index(self):
        language_tag = get_active_language_tag(self)
        if language_tag:
            return language_tag.code.startswith('es')
        return False

    @property
    def tags(self):
        return list(self.topics.names())

    @property
    def product_allowed_in(self):
        if (
            self.location_restriction and
            self.location_restriction.restriction_type == AbstractLocationRestrictionModel.ALLOWLIST
        ):
            return get_location_restriction(self.location_restriction)
        return EMPTY_LOCATION_RESTRICTION_LIST

    @property
    def product_blocked_in(self):
        if (
            self.location_restriction and
            self.location_restriction.restriction_type == AbstractLocationRestrictionModel.BLOCKLIST
        ):
            return get_location_restriction(self.location_restriction)
        return EMPTY_LOCATION_RESTRICTION_LIST

    @property
    def should_index(self):
        """Only index courses in the edX catalog with a non-hidden advertiseable course run, at least one owner, and
        a marketing url slug"""
        return (len(self.owners) > 0 and
                self.active_url_slug and
                self.partner.name == 'edX' and
                self.availability_level and
                bool(self.advertised_course_run) and
                not self.advertised_course_run.hidden)

    @property
    def should_index_spanish(self):
        return (self.should_index and
                self.type.slug != CourseType.EXECUTIVE_EDUCATION_2U and
                self.type.slug != CourseType.BOOTCAMP_2U)

    @property
    def availability_rank(self):
        today_midnight = datetime.datetime.now(pytz.UTC).replace(hour=0, minute=0, second=0, microsecond=0)
        if self.advertised_course_run:
            if self.advertised_course_run.is_current_and_still_upgradeable():
                return 1
            paid_seat_enrollment_end = self.advertised_course_run.get_paid_seat_enrollment_end()
            if paid_seat_enrollment_end and paid_seat_enrollment_end > today_midnight:
                return 2
            if datetime.datetime.now(pytz.UTC) >= self.advertised_course_run.start:
                return 3
            return self.advertised_course_run.start.timestamp()
        return None  # Algolia will deprioritize entries where a ranked field is empty


class AlgoliaProxyProgram(Program, AlgoliaBasicModelFieldsMixin):

    class Meta:
        proxy = True

    @property
    def product_type(self):
        if self.is_2u_degree_program:
            return '2U Degree'
        return 'Program'

    @property
    def product_title(self):
        return self.title

    @property
    def primary_description(self):
        return self.subtitle

    @property
    def secondary_description(self):
        return self.overview

    @property
    def tertiary_description(self):
        return ','.join([expected.value for expected in self.expected_learning_items.all()])

    @property
    def custom_object_id(self):
        return f'program-{self.uuid}'

    @property
    def product_card_image_url(self):
        if self.card_image:
            return self.card_image.url
        # legacy field for programs with images hosted outside of discovery
        return self.card_image_url

    @property
    def product_weeks_to_complete(self):
        # The field `weeks_to_complete` for Programs is now deprecated.
        return None

    @property
    def product_min_effort(self):
        return self.min_hours_effort_per_week

    @property
    def product_max_effort(self):
        return self.max_hours_effort_per_week

    @property
    def subject_names(self):
        return [subject.name for subject in self.subjects]

    @property
    def partner_names(self):
        return [org['name'] for org in get_owners(self)]

    @property
    def partner_keys(self):
        return [org['key'] for org in get_owners(self)]

    @property
    def levels(self):
        return list(dict.fromkeys([getattr(course.level_type, 'name_t', None) for course in self.courses.all()]))

    @property
    def active_languages(self):
        return list(dict.fromkeys([get_active_language(course) for course in self.courses.all()]))

    @property
    def expected_learning_items_values(self):
        return [item.value for item in self.expected_learning_items.all()]

    @property
    def owners(self):
        return get_owners(self)

    @property
    def staff_slugs(self):
        return [person.slug for person in self.staff]

    @property
    def course_titles(self):
        return [course.title for course in self.courses.all()]

    @property
    def program_types(self):
        if self.type:
            return [self.type.name]
        return None

    @property
    def tags(self):
        return [topic.name for topic in self.topics]

    @property
    def product_allowed_in(self):
        if (
            hasattr(self, 'location_restriction') and
            self.location_restriction.restriction_type == AbstractLocationRestrictionModel.ALLOWLIST
        ):
            return get_location_restriction(self.location_restriction)
        return EMPTY_LOCATION_RESTRICTION_LIST

    @property
    def product_blocked_in(self):
        if (
            hasattr(self, 'location_restriction') and
            self.location_restriction.restriction_type == AbstractLocationRestrictionModel.BLOCKLIST
        ):
            return get_location_restriction(self.location_restriction)
        return EMPTY_LOCATION_RESTRICTION_LIST

    @property
    def availability_level(self):
        # Master's and 2U programs don't have courses in the same way that our other programs do.
        # We got confirmation from masters POs that we should make masters Programs always
        # 'Available now'
        if self.type and self.type.slug in [
            ProgramType.MASTERS,
            ProgramType.BACHELORS,
            ProgramType.DOCTORATE,
            ProgramType.LICENSE,
        ]:
            return _('Available now')

        all_courses = self.courses.all()
        availability = set()

        for course in all_courses:
            course_status = get_course_availability(course)
            for status in course_status:
                availability.add(status)

        return list(availability)

    @property
    def promoted_in_spanish_index(self):
        all_course_languages = [get_active_language_tag(course) for course in self.courses.all()]
        all_course_languages = [tag for tag in all_course_languages if tag is not None]
        return any(tag.code.startswith('es') for tag in all_course_languages)

    @property
    def should_index(self):
        # marketing_url and program_type should never be null, but include as a sanity check
        return (len(self.owners) > 0 and
                self.marketing_url and
                self.program_types and
                self.status == ProgramStatus.Active and
                self.availability_level and
                self.partner.name == 'edX' and
                not self.hidden)

    @property
    def should_index_spanish(self):
        return self.should_index

    @property
    def is_2u_degree_program(self):
        return hasattr(self, 'degree') and hasattr(self.degree, 'additional_metadata')


class SearchDefaultResultsConfiguration(models.Model):
    index_name = models.CharField(max_length=32, unique=True)
    programs = SortedManyToManyField(Program, blank=True, null=True, limit_choices_to={'status': ProgramStatus.Active})
    courses = SortedManyToManyField(Course, blank=True, null=True, limit_choices_to={'draft': 0})
