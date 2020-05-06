import datetime

import pytz
from django.db import models
from django.utils.translation import activate
from django.utils.translation import ugettext_lazy as _

from course_discovery.apps.course_metadata.choices import CourseRunStatus, ProgramStatus
from course_discovery.apps.course_metadata.models import Course, Program, ProgramType


# Utility methods used by both courses and programs
def get_active_language(course):
    if course.advertised_course_run and course.advertised_course_run.language:
        return course.advertised_course_run.language.translated_macrolanguage
    return None


def activate_product_language(product):
    language = getattr(product, 'language', 'en')
    activate(language)


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

    search_fields = ['partner_names', 'product_title', 'primary_description', 'secondary_description',
                     'tertiary_description']
    facet_fields = ['availability_level', 'subject_names', 'levels', 'active_languages']
    ranking_fields = ['availability_rank', 'product_recent_enrollment_count', 'is_prof_cert_program']
    result_fields = ['product_marketing_url', 'product_card_image_url', 'product_uuid', 'active_run_key',
                     'active_run_start', 'active_run_type', 'owners', 'program_types', 'course_titles']
    object_id_field = ['custom_object_id', ]
    fields = search_fields + facet_fields + ranking_fields + result_fields + object_id_field
    for field in fields:
        def _closure(name):
            def _wrap(self, *args, **kwargs):  # pylint: disable=unused-argument
                return getattr(self.product, name, None)
            return _wrap
        setattr(cls, field, _closure(field))
    return cls


def get_course_availability(course):
    all_runs = course.course_runs.filter(status=CourseRunStatus.Published)

    if len([course_run for course_run in all_runs if
            course_run.is_current()]) > 0:
        return _('Available now')
    elif len([course_run for course_run in all_runs if
              course_run.is_upcoming()]) > 0:
        return _('Upcoming')
    elif len(all_runs) > 0:
        return _('Archived')
    else:
        return None

# Proxies Program model in order to trick Algolia into thinking this is a single model so it doesn't error.
# No model-specific attributes or methods are actually used.


@delegate_attributes
class AlgoliaProxyProduct(Program):
    class Meta:
        proxy = True

    def __init__(self, product, language='en'):
        super().__init__()
        self.product = product
        self.product.language = language

    def product_type(self):
        return getattr(type(self.product), 'product_type', None)

    # should_index is called differently from algoliasearch_django, can't use the delegate_attributes trick
    def should_index(self):
        return getattr(self.product, 'should_index', True)


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

    product_type = 'Course'

    class Meta:
        proxy = True

    @property
    def custom_object_id(self):
        return 'course-{uuid}'.format(uuid=self.uuid)

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
        activate_product_language(self)
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
    def levels(self):
        activate_product_language(self)
        level = getattr(self.level_type, 'name_t', None)
        if level:
            return [level]
        return None

    @property
    def subject_names(self):
        activate_product_language(self)
        return [subject.name for subject in self.subjects.all()]

    @property
    def program_types(self):
        activate_product_language(self)
        return [program.type.name_t for program in self.programs.all()]

    @property
    def product_card_image_url(self):
        if self.image:
            return getattr(self.image, 'url', None)
        return None

    @property
    def owners(self):
        return get_owners(self)

    @property
    def is_prof_cert_program(self):
        return False

    @property
    def should_index(self):
        """Only index courses in the edX catalog with a non-hidden advertiseable course run, at least one owner, and
        a marketing url slug"""
        return (len(self.owners) > 0 and
                self.active_url_slug and
                self.partner.name == 'edX' and
                self.availability_level is not None and
                bool(self.advertised_course_run) and
                not self.advertised_course_run.hidden)

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

    product_type = 'Program'

    class Meta:
        proxy = True

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
        return 'program-{uuid}'.format(uuid=self.uuid)

    @property
    def product_card_image_url(self):
        return self.card_image_url

    @property
    def subject_names(self):
        activate_product_language(self)
        return [subject.name for subject in self.subjects]

    @property
    def partner_names(self):
        return [org['name'] for org in get_owners(self)]

    @property
    def levels(self):
        activate_product_language(self)
        return list(dict.fromkeys([getattr(course.level_type, 'name_t', None) for course in self.courses.all()]))

    @property
    def active_languages(self):
        activate_product_language(self)
        return list(dict.fromkeys([get_active_language(course) for course in self.courses.all()]))

    @property
    def expected_learning_items_values(self):
        return [item.value for item in self.expected_learning_items.all()]

    @property
    def owners(self):
        return get_owners(self)

    @property
    def course_titles(self):
        return [course.title for course in self.courses.all()]

    @property
    def program_types(self):
        activate_product_language(self)
        if self.type:
            return [self.type.name_t]
        return None

    @property
    def availability_level(self):
        all_courses = self.courses.all()

        if len([course for course in all_courses if get_course_availability(course) == 'Available now']) > 0:
            return _('Available now')
        elif len([course for course in all_courses if get_course_availability(course) == 'Upcoming']) > 0:
            return _('Upcoming')
        elif len([course for course in all_courses if get_course_availability(course) == 'Archived']) > 0:
            return _('Archived')
        else:
            return None

    @property
    def is_prof_cert_program(self):
        return self.type and self.type.slug == ProgramType.PROFESSIONAL_CERTIFICATE

    @property
    def should_index(self):
        # marketing_url and program_type should never be null, but include as a sanity check
        return (len(self.owners) > 0 and
                self.marketing_url and
                self.program_types and
                self.status == ProgramStatus.Active and
                self.availability_level is not None and
                self.partner.name == 'edX')
