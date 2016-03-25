from haystack import indexes

from course_discovery.apps.course_metadata.models import Course


class CourseIndex(indexes.SearchIndex, indexes.Indexable):
    text = indexes.CharField(document=True, use_template=True)
    key = indexes.CharField(model_attr='key', stored=True)
    title = indexes.CharField(model_attr='title')
    organizations = indexes.MultiValueField()
    short_description = indexes.CharField(model_attr='short_description', null=True)
    full_description = indexes.CharField(model_attr='full_description', null=True)
    level_type = indexes.CharField(model_attr='level_type__name', null=True)

    def prepare_organizations(self, obj):
        return [organization.name for organization in obj.organizations.all()]

    def get_model(self):
        return Course

    def index_queryset(self, using=None):
        return self.get_model().objects.all()

    def get_updated_field(self):  # pragma: no cover
        return 'modified'
