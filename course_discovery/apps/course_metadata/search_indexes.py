from haystack import indexes

from course_discovery.apps.course_metadata.models import Course


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
