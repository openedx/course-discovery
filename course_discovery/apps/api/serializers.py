from django.utils.translation import ugettext_lazy as _
from rest_framework import serializers

from course_discovery.apps.catalogs.models import Catalog
from course_discovery.apps.course_metadata.models import(
    Course, CourseRun, Image, Organization, Person, Prerequisite, Seat, Subject, Video
)


class TimestampModelSerializer(serializers.ModelSerializer):
    modified = serializers.DateTimeField()


class NamedModelSerializer(serializers.ModelSerializer):
    name = serializers.CharField()

    class Meta(object):
        fields = ('name', )


class SubjectSerializer(NamedModelSerializer):
    class Meta(NamedModelSerializer.Meta):
        model = Subject


class PrerequisiteSerializer(NamedModelSerializer):
    class Meta(NamedModelSerializer.Meta):
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


class SeatSerializer(serializers.ModelSerializer):
    type = serializers.ChoiceField(
        choices=[name for name, __ in Seat.SEAT_TYPE_CHOICES]
    )
    price = serializers.DecimalField(
        decimal_places=Seat.PRICE_FIELD_CONFIG['decimal_places'],
        max_digits=Seat.PRICE_FIELD_CONFIG['max_digits']
    )
    currency = serializers.SlugRelatedField(read_only=True, slug_field='code')
    upgrade_deadline = serializers.DateTimeField()
    credit_provider = serializers.CharField()
    credit_hours = serializers.IntegerField()

    class Meta(object):
        model = Seat
        fields = ('type', 'price', 'currency', 'upgrade_deadline', 'credit_provider', 'credit_hours', )


class PersonSerializer(serializers.ModelSerializer):
    profile_image = ImageSerializer()

    class Meta(object):
        model = Person
        fields = ('name', 'title', 'bio', 'profile_image',)


class OrganizationSerializer(serializers.ModelSerializer):
    logo_image = ImageSerializer()

    class Meta(object):
        model = Organization
        fields = ('name', 'description', 'logo_image', 'homepage_url', )


class CatalogSerializer(serializers.ModelSerializer):
    class Meta(object):
        model = Catalog
        fields = ('id', 'name', 'query', 'courses_count',)


class CourseSerializer(TimestampModelSerializer):
    level_type = serializers.SlugRelatedField(read_only=True, slug_field='name')
    subjects = SubjectSerializer(many=True)
    prerequisites = PrerequisiteSerializer(many=True)
    expected_learning_items = serializers.SlugRelatedField(many=True, read_only=True, slug_field='value')
    image = ImageSerializer()
    video = VideoSerializer()
    owners = OrganizationSerializer(many=True)
    sponsors = OrganizationSerializer(many=True)

    class Meta(object):
        model = Course
        fields = (
            'key', 'title', 'short_description', 'full_description', 'level_type', 'subjects',
            'prerequisites', 'expected_learning_items', 'image', 'video', 'owners', 'sponsors',
            'modified',
        )


class CourseRunSerializer(TimestampModelSerializer):
    content_language = serializers.SlugRelatedField(read_only=True, slug_field='code', source='language')
    transcript_languages = serializers.SlugRelatedField(many=True, read_only=True, slug_field='code')
    image = ImageSerializer()
    video = VideoSerializer()
    seats = SeatSerializer(many=True)
    instructors = PersonSerializer(many=True)
    staff = PersonSerializer(many=True)

    class Meta(object):
        model = CourseRun
        fields = (
            'key', 'title', 'short_description', 'full_description', 'start', 'end',
            'enrollment_start', 'enrollment_end', 'announcement', 'image', 'video', 'seats',
            'content_language', 'transcript_languages', 'instructors', 'staff',
            'pacing_type', 'min_effort', 'max_effort', 'modified',
        )


class ContainedCoursesSerializer(serializers.Serializer):  # pylint: disable=abstract-method
    courses = serializers.DictField(
        child=serializers.BooleanField(),
        help_text=_('Dictionary mapping course IDs to boolean values')
    )
