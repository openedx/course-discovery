from django.utils.translation import ugettext_lazy as _
from rest_framework import serializers

from course_discovery.apps.catalogs.models import Catalog


class CatalogSerializer(serializers.ModelSerializer):
    url = serializers.HyperlinkedIdentityField(view_name='api:v1:catalog-detail', lookup_field='id')

    class Meta(object):
        model = Catalog
        fields = ('id', 'name', 'query', 'url',)


class CourseSerializer(serializers.ModelSerializer):
    key = serializers.CharField(help_text=_('Course Key'))
    name = serializers.CharField(help_text=_('Course name'))

    class Meta(object):
        model = Catalog
        fields = ('key', 'name',)


class ContainedCoursesSerializer(serializers.Serializer):  # pylint: disable=abstract-method
    courses = serializers.DictField(
        child=serializers.BooleanField(),
        help_text=_('Dictionary mapping course IDs to boolean values')
    )
