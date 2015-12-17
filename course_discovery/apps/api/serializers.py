from django.utils.translation import ugettext_lazy as _
from rest_framework import serializers

from course_discovery.apps.catalogs.models import Catalog


class CatalogSerializer(serializers.ModelSerializer):
    class Meta(object):
        model = Catalog
        fields = ('id', 'name', 'query',)


class CourseSerializer(serializers.Serializer):  # pylint: disable=abstract-method
    id = serializers.CharField(help_text=_('Course ID'))
    name = serializers.CharField(help_text=_('Course name'))


class ContainedCoursesSerializer(serializers.Serializer):  # pylint: disable=abstract-method
    courses = serializers.DictField(
        child=serializers.BooleanField(),
        help_text=_('Dictionary mapping course IDs to boolean values')
    )
