from haystack import indexes
from opaque_keys.edx.keys import CourseKey

from course_catalog.apps.course_metadata.models import Course, CourseRun


class CourseIndex(indexes.SearchIndex, indexes.Indexable):
    text = indexes.CharField(document=True, use_template=True)
    key = indexes.CharField(model_attr='key', stored=True)
    title = indexes.CharField(model_attr='title')
    short_description = indexes.CharField(model_attr='short_description', null=True)
    full_description = indexes.CharField(model_attr='full_description', null=True)
    level_type = indexes.CharField(model_attr='level_type__name', null=True)
    course_runs = indexes.MultiValueField()
    expected_learning_items = indexes.MultiValueField()
    organizations = indexes.MultiValueField()
    prerequisites = indexes.MultiValueField()
    subjects = indexes.MultiValueField()

    def prepare_course_runs(self, obj):
        return [course_run.key for course_run in obj.course_runs.all()]

    def prepare_expected_learning_items(self, obj):
        return [item.value for item in obj.expected_learning_items.all()]

    def prepare_organizations(self, obj):
        return ['{key}: {name}'.format(key=organization.key, name=organization.name) for organization in
                obj.organizations.all()]

    def prepare_prerequisites(self, obj):
        return [prerequisite.name for prerequisite in obj.prerequisites.all()]

    def prepare_subjects(self, obj):
        return [subject.name for subject in obj.subjects.all()]

    def get_model(self):
        return Course

    def index_queryset(self, using=None):
        return self.get_model().objects.all()

    def get_updated_field(self):  # pragma: no cover
        return 'modified'


class CourseRunIndex(indexes.SearchIndex, indexes.Indexable):
    text = indexes.CharField(document=True, use_template=True)
    course_key = indexes.CharField(model_attr='course__key', stored=True)
    key = indexes.CharField(model_attr='key', stored=True)
    org = indexes.CharField()
    number = indexes.CharField()
    title = indexes.CharField(model_attr='title_override', null=True)
    start = indexes.DateTimeField(model_attr='start', null=True)
    end = indexes.DateTimeField(model_attr='end', null=True)
    enrollment_start = indexes.DateTimeField(model_attr='enrollment_start', null=True)
    enrollment_end = indexes.DateTimeField(model_attr='enrollment_end', null=True)
    announcement = indexes.DateTimeField(model_attr='announcement', null=True)
    min_effort = indexes.IntegerField(model_attr='min_effort', null=True)
    max_effort = indexes.IntegerField(model_attr='max_effort', null=True)
    language = indexes.CharField(null=True)
    transcript_languages = indexes.MultiValueField()
    pacing_type = indexes.CharField(model_attr='pacing_type', null=True)

    def _prepare_language(self, language):
        return '{code}: {name}'.format(code=language.code, name=language.name)

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

    def get_model(self):
        return CourseRun

    def get_updated_field(self):  # pragma: no cover
        return 'modified'
