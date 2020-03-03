from django.utils.translation import activate

from course_discovery.apps.course_metadata.models import Course, Program


def get_active_language(course):
    if course.advertised_course_run:
        return course.advertised_course_run.language.name
    return None


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

    def partner_name(self):
        return self.partner.name

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
        def logo_image(owner):
            image = getattr(owner, 'logo_image', None)
            if image:
                return image.url
            return None

        return [{'key': o.key, 'logoImageUrl': getattr(logo_image(o), 'url', None)} for o in
                self.authoring_organizations.all()]


class AlgoliaProxyProgram(Program):

    class Meta:
        proxy = True

    def subject_names(self):
        activate('en')
        return [subject.name for subject in self.subjects]

    def partner_name(self):
        return self.partner.name

    def levels(self):
        return list(dict.fromkeys([getattr(course.level_type, 'name', None) for course in self.courses.all()]))

    def active_languages(self):
        return [get_active_language(course) for course in self.courses.all()]

    def expected_learning_items_values(self):
        return [item.value for item in self.expected_learning_items.all()]

    def owners(self):
        def logo_image(owner):
            image = getattr(owner, 'logo_image', None)
            if image:
                return image.url
            return None

        return [{'key': o.key, 'logoImageUrl': getattr(logo_image(o), 'url', None)} for o in
                self.authoring_organizations.all()]

    def course_titles(self):
        return [course.title for course in self.courses.all()]

    def program_type(self):
        return self.type.slug
