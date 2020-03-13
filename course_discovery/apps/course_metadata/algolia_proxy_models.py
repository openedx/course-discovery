import datetime

import pytz
from django.utils.translation import activate

from course_discovery.apps.course_metadata.models import Course, Program


def get_active_language(course):
    if course.advertised_course_run and course.advertised_course_run.language:
        return course.advertised_course_run.language.name
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


class AlgoliaProxyCourse(Course):

    class Meta:
        proxy = True

    def active_languages(self):
        return [get_active_language(self)]



    def availability(self):
        return

    def partner_names(self):
        return [org['name'] for org in get_owners(self)]


    def subject_names(self):
        activate('en')


    def program_types(self):
        return [program.type.name for program in self.programs.all()]

    def card_image_url(self):
        pass

    def owners(self):
        return get_owners(self)

    def should_index(self):
        return (len(self.owners()) > 0 and
                self.active_url_slug and
                self.partner.name == 'edX' and
                bool(self.advertised_course_run))



class AlgoliaProxyProgram(Program):

    class Meta:
        proxy = True

    def availability_level(self):
        if isinstance(self, AlgoliaProxyProgram):
            return self.status.capitalize()
        status = getattr(self.advertised_course_run, 'availability', None)
        if status:
            return status.capitalize()
        return None

    def primary_description(self):
        if isinstance(self, AlgoliaProxyProgram):
            return self.overview
        return self.short_description

    def secondary_description(self):
        if isinstance(self, AlgoliaProxyProgram):
            return ','.join([item.value for item in self.expected_learning_items.all()])
        return self.full_description

    def tertiary_description(self):
        if isinstance(self, AlgoliaProxyProgram):
            return self.subtitle
        return self.outcome

    def card_image_url(self):
        if isinstance(self, AlgoliaProxyProgram):
            return self.card_image_url
        if self.image:
            return getattr(self.image, 'url', None)
        return None

    def subject_names(self):
        activate('en')
        if isinstance(self, AlgoliaProxyProgram):
            return [subject.name for subject in self.subjects]
        return [subject.name for subject in self.subjects.all()]

    def partner_names(self):
        return [org['name'] for org in get_owners(self)]

    def levels(self):
        if isinstance(self, AlgoliaProxyProgram):
            return list(dict.fromkeys([getattr(course.level_type, 'name', None) for course in self.courses.all()]))
        return [getattr(self.level_type, 'name', None)]

    def active_languages(self):
        if isinstance(self, AlgoliaProxyProgram):
            return [get_active_language(course) for course in self.courses.all()]
        return [get_active_language(self)]

    def owners(self):
        return get_owners(self)

    def course_titles(self):
        if isinstance(self, AlgoliaProxyProgram):
            return [course.title for course in self.courses.all()]
        return None

    def program_types(self):
        if isinstance(self, AlgoliaProxyProgram):
            if self.type:
                return [self.type.slug]
            return None
        return [program.type.name for program in self.programs.all()]

    def active_run_key(self):
        if isinstance(self, AlgoliaProxyProgram):
            return None
        return getattr(self.advertised_course_run, 'key', None)

    def active_run_start(self):
        if isinstance(self, AlgoliaProxyProgram):
            return None
        return getattr(self.advertised_course_run, 'start', None)

    def active_run_type(self):
        if isinstance(self, AlgoliaProxyProgram):
            return None
        return getattr(self.advertised_course_run, 'type', None)

    def availability_rank(self):
        if isinstance(self, AlgoliaProxyProgram):
            return None
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

    def objectID(self):
        if isinstance(self, AlgoliaProxyProgram):
            return 'program-{u}'.format(u=self.uuid)
        return 'course-{u}'.format(u=self.uuid)

    def product_type(self):
        if isinstance(self, AlgoliaProxyProgram):
            return 'Program'
        return 'Course'

    def should_index(self):
        if self['type'] == "pgm":
            program_obj = AlgoliaProxyProgram.objects.get(id=self['id'])
        # marketing_url and program_type should never be null, but include as a sanity check
            return len(program_obj.owners()) > 0 and program_obj.marketing_url and program_obj.program_types() and program_obj.partner.name == 'edX'
        course_obj = AlgoliaProxyCourse.objects.get(id=self['id'])
        return (len(course_obj.owners()) > 0 and
                course_obj.active_url_slug and
                course_obj.partner.name == 'edX' and
                bool(course_obj.advertised_course_run))

