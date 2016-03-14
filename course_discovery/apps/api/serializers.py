from django.utils.translation import ugettext_lazy as _
from rest_framework import serializers

from course_discovery.apps.catalogs.models import Catalog


class CatalogSerializer(serializers.ModelSerializer):
    url = serializers.HyperlinkedIdentityField(view_name='api:v1:catalog-detail', lookup_field='id')

    class Meta(object):
        model = Catalog
        fields = ('id', 'name', 'query', 'url',)


class LinkSerializer(serializers.Serializer):  # pylint: disable=abstract-method
    name = serializers.CharField(help_text=_('Link name'))
    uri = serializers.URLField(help_text=_('Link reference'))


class SeatSerializer(serializers.Serializer):  # pylint: disable=abstract-method
    type = serializers.ChoiceField(
        choices=('audit', 'honor', 'verified', 'credit', 'professional'),
        help_text=_('Enrollment mode for the seat')
    )
    price = serializers.FloatField(help_text=_('Price of the seat'))
    currency = serializers.CharField(help_text=_('Currency for the seat'))
    upgrade_deadline = serializers.DateTimeField(help_text=_('Deadline to upgrade (for verified and credit seats)'))
    credit_provider = serializers.CharField(help_text=_('Institution granting credit (for credit seats)'))
    credit_hours = serializers.IntegerField(help_text=_('Number of credit hours (for credit seats)'))


class EffortSerializer(serializers.Serializer):  # pylint: disable=abstract-method
    min = serializers.IntegerField(help_text=_('Minimum effort for the course'))
    max = serializers.IntegerField(help_text=_('Maximum effort for the course'))


class ImageSerializer(serializers.Serializer):  # pylint: disable=abstract-method
    uri = serializers.URLField()
    height = serializers.IntegerField(help_text=_('Height of the image'))
    width = serializers.IntegerField(help_text=_('Width of the image'))
    description = serializers.CharField(help_text=_('Description of the image'))

class VideoSerializer(serializers.Serializer):  # pylint: disable=abstract-method
    uri = serializers.URLField()
    name = serializers.CharField(help_text=_('Name of the video'))
    description = serializers.CharField(help_text=_('Description of the video'))
    type = serializers.ChoiceField(
        choices=('youtube', 'brightcove', 'vimeo'),
        help_text=_('Source of the video')
    )
    image = ImageSerializer()

class SyllabusSerializer(serializers.Serializer):  # pylint: disable=abstract-method
    title = serializers.CharField(help_text=_('Title of the syllabus'))
    contents = serializers.ListField(
        child=LinkSerializer(),
        help_text=_('Syllabus contents')
    )


class OrgSerializer(serializers.Serializer):  # pylint: disable=abstract-method
    id = serializers.IntegerField()
    name = serializers.CharField(help_text=_('Organization name'))
    image = ImageSerializer()
    description = serializers.CharField(help_text=_('Description of the organization'))
    uri = serializers.URLField(help_text=_('Link to the organization'))


class StaffSerializer(serializers.Serializer):  # pylint: disable=abstract-method
    name = serializers.CharField(help_text=_("Staff member's name"))
    uri = serializers.URLField(help_text=_("Link to staff member's about page"))
    title = serializers.CharField(help_text=_("Staff member's title"))
    org = OrgSerializer()
    image = ImageSerializer()


class AdditionalMediaSerializer(serializers.Serializer):  # pylint: disable=abstract-method
    images = serializers.ListField(child=ImageSerializer())
    videos = serializers.ListField(child=VideoSerializer())


class CourseSerializer(serializers.Serializer):  # pylint: disable=abstract-method
    id = serializers.CharField(help_text=_('Course ID'))
    uri = serializers.URLField(help_text=_('Link to edX about page for the course'))
    name = serializers.CharField(help_text=_('Course name'))
    short_description = serializers.CharField(help_text=_('Short description of the course'))
    long_description = serializers.CharField(help_text=_('Long description of the course'))
    expected_learnings = serializers.ListField(
        child=serializers.CharField(),
        help_text=_('List of skills students will learn')
    )
    level_type = serializers.ChoiceField(
        choices=('introductory', 'intermediate', 'advanced'),
        help_text=_('Course difficulty level')
    )
    subjects = serializers.ListField(
        child=LinkSerializer(),
        help_text=_('Related subjects')
    )
    prerequisites = serializers.ListField(
        child=LinkSerializer(),
        help_text=_('Prerequisites for the course')
    )
    effort = EffortSerializer()
    image = ImageSerializer()
    video = VideoSerializer()
    orgs = serializers.ListField(
        child=OrgSerializer(),
        help_text=_('Course organizations')
    )
    sponsors = serializers.ListField(
        child=OrgSerializer(),
        help_text=_('Course sponsors')
    )
    additional_media = AdditionalMediaSerializer()


class CourseRunSerializer(serializers.Serializer):  #pylint: disable=abstract-method
    id = serializers.CharField(help_text=_('Course run ID'))
    start = serializers.DateTimeField(help_text=_('Course start date'))
    end = serializers.DateTimeField(help_text=_('Course end date'))
    enrollment_period_start = serializers.DateTimeField(help_text=_('Start date for course enrollment'))
    enrollment_period_end = serializers.DateTimeField(help_text=_('End date for course enrollment'))
    pacing_type = serializers.ChoiceField(
        choices=('self_paced', 'instructor_paced'),
        help_text=_('Course pacing')
    )
    seats = serializers.ListField(
        child=SeatSerializer(),
        help_text=_('Seats for the course run')
    )
    content_language = serializers.CharField(help_text=_('Content language for the course run'))
    transcript_languages = serializers.ListField(
        child=serializers.CharField(),
        help_text=_('Languages available for video transcripts')
    )
    syllabus = SyllabusSerializer()
    staff = serializers.ListField(
        child=StaffSerializer(),
        help_text=_('Course staff')
    )
    program = OrgSerializer()
    course = CourseSerializer()


class ContainedCoursesSerializer(serializers.Serializer):  # pylint: disable=abstract-method
    courses = serializers.DictField(
        child=serializers.BooleanField(),
        help_text=_('Dictionary mapping course IDs to boolean values')
    )
