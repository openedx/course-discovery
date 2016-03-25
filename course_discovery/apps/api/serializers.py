from django.utils.translation import ugettext_lazy as _
from rest_framework import serializers

from course_discovery.apps.catalogs.models import Catalog
from course_discovery.apps.course_metadata.models import(
    Course, CourseOrganization, Image, Subject, Organization, Prerequisite, Video
)


class TimestampModelSerializer(serializers.ModelSerializer):
    modified = serializers.DateTimeField()


class LinkObjectSerializer(serializers.ModelSerializer):
    name = serializers.CharField()

    class Meta(object):
        fields = ('name', )


class SubjectSerializer(LinkObjectSerializer):
    class Meta(LinkObjectSerializer.Meta):
        model = Subject


class PrerequisiteSerializer(LinkObjectSerializer):
    class Meta(LinkObjectSerializer.Meta):
        model = Prerequisite


class MediaSerializer(serializers.ModelSerializer):
    src = serializers.CharField()
    description = serializers.CharField()


class ImageSerializer(MediaSerializer):
    height = serializers.IntegerField()
    width = serializers.IntegerField()

    class Meta(object):
        model = Image
        fields = ('src', 'description', 'height', 'width')


class VideoSerializer(MediaSerializer):
    image = ImageSerializer()

    class Meta(object):
        model = Video
        fields = ('src', 'description', 'image', )


class OrganizationSerializer(serializers.ModelSerializer):
    name = serializers.CharField()
    logo_image = ImageSerializer()
    description = serializers.CharField()
    homepage_url = serializers.CharField()

    class Meta(object):
        model = Organization
        fields = ('name', 'description', 'logo_image', 'homepage_url', )


class CatalogSerializer(serializers.ModelSerializer):
    url = serializers.HyperlinkedIdentityField(view_name='api:v1:catalog-detail', lookup_field='id')

    class Meta(object):
        model = Catalog
        fields = ('id', 'name', 'query', 'url',)


class CourseSerializer(TimestampModelSerializer):
    level_type = serializers.SlugRelatedField(read_only=True, slug_field='name')
    subjects = SubjectSerializer(many=True)
    prerequisites = PrerequisiteSerializer(many=True)
    expected_learning_items = serializers.SlugRelatedField(many=True, read_only=True, slug_field='value')
    image = ImageSerializer()
    video = VideoSerializer()
    owners = serializers.SerializerMethodField('get_owners_list')
    sponsors = serializers.SerializerMethodField('get_sponsors_list')

    def get_owners_list(self, obj):
        owners = obj.organizations.filter(courseorganization__relation_type=CourseOrganization.OWNER)
        return OrganizationSerializer(owners, many=True).data

    def get_sponsors_list(self, obj):
        owners = obj.organizations.filter(courseorganization__relation_type=CourseOrganization.SPONSOR)
        return OrganizationSerializer(owners, many=True).data

    class Meta(object):
        model = Course
        fields = (
            'key', 'title', 'short_description', 'full_description', 'level_type', 'subjects',
            'prerequisites', 'expected_learning_items', 'image', 'video', 'owners', 'sponsors',
            'modified',
        )


class ContainedCoursesSerializer(serializers.Serializer):  # pylint: disable=abstract-method
    courses = serializers.DictField(
        child=serializers.BooleanField(),
        help_text=_('Dictionary mapping course IDs to boolean values')
    )
