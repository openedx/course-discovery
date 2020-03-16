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

    def active_run_language(self):
        return get_active_language(self)

    def active_run_key(self):
        return getattr(self.advertised_course_run, 'key', None)

    def active_run_start(self):
        return getattr(self.advertised_course_run, 'start', None)

    def active_run_type(self):
        return getattr(self.advertised_course_run, 'type', None)

    def availability(self):
        return getattr(self.advertised_course_run, 'availability', None)

    def partner_names(self):
        return [org['name'] for org in get_owners(self)]

    def level_type_name(self):
        return getattr(self.level_type, 'name', None)

    def subject_names(self):
        activate('en')
        return [subject.name for subject in self.subjects.all()]

    def program_types(self):
        return [program.type.name for program in self.programs.all()]

    def image_src(self):
        if self.image:
            return getattr(self.image, 'url', None)
        return None

    def owners(self):
        return get_owners(self)

    def should_index(self):
        return (len(self.owners()) > 0 and
                self.active_url_slug and
                self.partner.name == 'edX' and
                bool(self.advertised_course_run))

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


class AlgoliaProxyProgram(Program):

    class Meta:
        proxy = True

    def subject_names(self):
        activate('en')
        return [subject.name for subject in self.subjects]

    def partner_names(self):
        return [org['name'] for org in get_owners(self)]

    def levels(self):
        return list(dict.fromkeys([getattr(course.level_type, 'name', None) for course in self.courses.all()]))

    def active_languages(self):
        return [get_active_language(course) for course in self.courses.all()]

    def expected_learning_items_values(self):
        return [item.value for item in self.expected_learning_items.all()]

    def owners(self):
        return get_owners(self)

    def course_titles(self):
        return [course.title for course in self.courses.all()]

    def program_type(self):
        if self.type:
            return self.type.slug
        return None

    def should_index(self):
        # marketing_url and program_type should never be null, but include as a sanity check
        return len(self.owners()) > 0 and self.marketing_url and self.program_type() and self.partner.name == 'edX'
