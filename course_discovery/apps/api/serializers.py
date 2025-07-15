import datetime

import pytz
from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db.models import Case
from django.db.models import When
from django.db.models.query import Prefetch
from rest_framework import serializers
from rest_framework.fields import (
    DictField, ListField
)

from course_discovery.apps.course_metadata.choices import CourseRunStatus
from course_discovery.apps.course_metadata.models import (
    Course, CourseRun, Program
)


User = get_user_model()

COMMON_IGNORED_FIELDS = ('text',)
COMMON_SEARCH_FIELD_ALIASES = {'q': 'text'}


class TimestampModelSerializer(serializers.ModelSerializer):
    """Serializer for timestamped models."""
    modified = serializers.DateTimeField()


class MinimalCourseRunSerializer(TimestampModelSerializer):

    @classmethod
    def prefetch_queryset(cls, queryset=None):
        # Explicitly check for None to avoid returning all CourseRuns when the
        # queryset passed in happens to be empty.
        queryset = queryset if queryset is not None else CourseRun.objects.all()

        return queryset.select_related('course')

    class Meta:
        model = CourseRun
        fields = (
            'key', 'uuid', 'title', 'status',
            'start', 'end', 'enrollment_start', 'enrollment_end'
        )


class CourseRunSerializer(MinimalCourseRunSerializer):
    """Serializer for the ``CourseRun`` model."""
    course = serializers.SlugRelatedField(read_only=True, slug_field='key')

    @classmethod
    def prefetch_queryset(cls, queryset=None):
        return super().prefetch_queryset(queryset=queryset)

    class Meta(MinimalCourseRunSerializer.Meta):
        fields = MinimalCourseRunSerializer.Meta.fields + (
            'course',
            'modified',
        )


class MinimalCourseSerializer(TimestampModelSerializer):
    course_runs = MinimalCourseRunSerializer(many=True)

    @classmethod
    def prefetch_queryset(cls, queryset=None, course_runs=None):
        # Explicitly check for None to avoid returning all Courses when the
        # queryset passed in happens to be empty.
        queryset = queryset if queryset is not None else Course.objects.all()

        return queryset.prefetch_related(
            Prefetch(
                'course_runs',
                queryset=MinimalCourseRunSerializer.prefetch_queryset(queryset=course_runs)),
        )

    class Meta:
        model = Course
        fields = ('key', 'uuid', 'title', 'course_runs')


class CourseSerializer(MinimalCourseSerializer):
    """Serializer for the ``Course`` model."""
    course_runs = CourseRunSerializer(many=True)

    @classmethod
    def prefetch_queryset(cls, org=None, queryset=None, course_runs=None, orgs=None):
        # Explicitly check for None to avoid returning all Courses when the
        # queryset passed in happens to be empty.
        filters = {}
        if org:
            filters = {'org': org}
        elif orgs:
            filters = {'org__in': orgs}
        queryset = queryset if queryset is not None else Course.objects.filter(**filters)

        return queryset.prefetch_related(
            Prefetch('course_runs', queryset=CourseRunSerializer.prefetch_queryset(queryset=course_runs)),
        )

    class Meta(MinimalCourseSerializer.Meta):
        model = Course
        fields = MinimalCourseSerializer.Meta.fields + (
            'modified', 'card_image_url',
        )


class MinimalProgramCourseSerializer(MinimalCourseSerializer):
    """
    Serializer used to filter out excluded course runs in a course associated with the program.

    Notes:
        This is shared by both MinimalProgramSerializer and ProgramSerializer!
    """
    course_runs = serializers.SerializerMethodField()

    def get_course_runs(self, course):
        course_runs = self.context['course_runs']
        course_runs = [course_run for course_run in course_runs if course_run.course == course]

        if self.context.get('published_course_runs_only'):
            course_runs = [course_run for course_run in course_runs if course_run.status == CourseRunStatus.Published]

        serializer_class = MinimalCourseRunSerializer
        if self.context.get('use_full_course_serializer', False):
            serializer_class = CourseRunSerializer

        return serializer_class(
            course_runs,
            many=True,
            context={
                'request': self.context.get('request'),
                'exclude_utm': self.context.get('exclude_utm'),
            }
        ).data


def _validate_comma_separated_languages_list(value):
    if isinstance(value, list):
        for lang in value:
            if lang not in settings.LANGUAGES_CODES:
                raise ValidationError('Invalid language code : {}'.format(lang))
    else:
        raise ValidationError('Invalid argument type : {}'.format(type(value)))


class MinimalProgramSerializer(serializers.ModelSerializer):
    courses = serializers.SerializerMethodField()
    languages = ListField(validators=[_validate_comma_separated_languages_list])

    @classmethod
    def prefetch_queryset(cls, orgs, *args, **kwargs):
        filters = {'orgs': orgs}            # A Program must be related with organizations.
        program_uuid = kwargs.get('uuid')
        if program_uuid:                    # Filter a Program with primary Key
            filters['uuid'] = program_uuid

        return Program.objects.filter(**filters).prefetch_related(
            # `type` is serialized by a third-party serializer. Providing this field name allows us to
            # prefetch `applicable_seat_types`, a m2m on `ProgramType`, through `type`, a foreign key to
            # `ProgramType` on `Program`.
            Prefetch(
                'courses',
                queryset=MinimalProgramCourseSerializer.prefetch_queryset()
            ),
        )

    class Meta:
        model = Program
        fields = (
            'uuid', 'title', 'status', 'orgs', 'visibility',
            'courses', 'card_image_url', 'duration', 'languages',
            'start', 'end', 'enrollment_start', 'enrollment_end'
        )
        read_only_fields = ('uuid', 'enrollment_start', 'enrollment_end')

    def get_courses(self, program):
        draft_program_courses_uuids = self.context.get('draft_program_courses_uuids')

        if draft_program_courses_uuids is not None:
            query_by_title = self.context.get('query_by_title')
            # For: Draft Program detail query with ORDER of UUIDs vector
            preserved = Case(
                *[When(uuid=pk, then=pos)
                  for pos, pk in enumerate(draft_program_courses_uuids)]
            )
            filters = {
                'uuid__in': draft_program_courses_uuids,  # UUIDs list of `Draft` Program in MongoDB.
            }
            if query_by_title:
                filters['title__icontains'] = query_by_title

            courses = Course.objects.filter(
                **filters
            ).order_by(preserved)
            course_runs = [
                run
                for course in courses.all()
                for run in course.course_runs.all()
            ]
        else:
            # For: Prod. Program detail query
            course_runs = list(program.course_runs)

            if self.context.get('marketable_enrollable_course_runs_with_archived'):
                marketable_enrollable_course_runs = set()
                for course in program.courses.all():
                    marketable_enrollable_course_runs.update(course.course_runs.marketable().enrollable())
                course_runs = list(set(course_runs).intersection(marketable_enrollable_course_runs))

            courses = program.courses.all()

        course_serializer = MinimalProgramCourseSerializer(
            courses,
            many=True,
            context={
                'request': self.context.get('request'),
                'published_course_runs_only': self.context.get('published_course_runs_only'),
                'exclude_utm': self.context.get('exclude_utm'),
                'program': program,
                'course_runs': course_runs,
                'use_full_course_serializer': self.context.get('use_full_course_serializer', False),
            }
        )

        return course_serializer.data

    def sort_courses(self, program, course_runs):
        """
        Sorting by enrollment start then by course start yields a list ordered by course start, with
        ties broken by enrollment start. This works because Python sorting is stable: two objects with
        equal keys appear in the same order in sorted output as they appear in the input.

        Courses are only created if there's at least one course run belonging to that course, so
        course_runs should never be empty. If it is, key functions in this method attempting to find the
        min of an empty sequence will raise a ValueError.
        """

        def min_run_enrollment_start(course):
            # Enrollment starts may be empty. When this is the case, we make the same assumption as
            # the LMS: no enrollment_start is equivalent to (offset-aware) datetime.datetime.min.
            min_datetime = datetime.datetime.min.replace(tzinfo=pytz.UTC)

            # Course runs excluded from the program are excluded here, too.
            #
            # If this becomes a candidate for optimization in the future, be careful sorting null values
            # in the database. PostgreSQL and MySQL sort null values as if they are higher than non-null
            # values, while SQLite does the opposite.
            #
            # For more, refer to https://docs.djangoproject.com/en/1.10/ref/models/querysets/#latest.
            _course_runs = [course_run for course_run in course_runs if course_run.course == course]

            # Return early if we have no course runs since min() will fail.
            if not _course_runs:
                return min_datetime

            run = min(_course_runs, key=lambda run: run.enrollment_start or min_datetime)

            return run.enrollment_start or min_datetime

        def min_run_start(course):
            # Course starts may be empty. Since this means the course can't be started, missing course
            # start date is equivalent to (offset-aware) datetime.datetime.max.
            max_datetime = datetime.datetime.max.replace(tzinfo=pytz.UTC)

            _course_runs = [course_run for course_run in course_runs if course_run.course == course]

            # Return early if we have no course runs since min() will fail.
            if not _course_runs:
                return max_datetime

            run = min(_course_runs, key=lambda run: run.start or max_datetime)

            return run.start or max_datetime

        courses = list(program.courses.all())
        courses.sort(key=min_run_enrollment_start)
        courses.sort(key=min_run_start)

        return courses


class ProgramSerializer(MinimalProgramSerializer):

    @classmethod
    def prefetch_queryset(cls, orgs, *args, **kwargs):
        """
        Prefetch the related objects that will be serialized with a `Program`.

        We use Prefetch objects so that we can prefetch and select all the way down the
        chain of related fields from programs to course runs (i.e., we want control over
        the querysets that we're prefetching).
        """
        filters = {'orgs': orgs}            # A Program must be related with organizations.
        program_uuid = kwargs.get('uuid')
        if program_uuid:                    # Filter a Program with primary Key
            filters['uuid'] = program_uuid

        return Program.objects.filter(**filters).prefetch_related(
            # `type` is serialized by a third-party serializer. Providing this field name allows us to
            # prefetch `applicable_seat_types`, a m2m on `ProgramType`, through `type`, a foreign key to
            # `ProgramType` on `Program`.
            # We need the full Course prefetch here to get CourseRun information that methods on the Program
            # model iterate across (e.g. language). These fields aren't prefetched by the minimal Course serializer.
            Prefetch('courses', queryset=CourseSerializer.prefetch_queryset(orgs=orgs)),
        )

    def get_applicable_seat_types(self, obj):
        if not obj.type:
            return []

        return list(obj.type.applicable_seat_types.values_list('slug', flat=True))

    class Meta(MinimalProgramSerializer.Meta):
        model = Program
        fields = MinimalProgramSerializer.Meta.fields + (
            'languages', 'description', 'duration', 'created', 'modified', 'creator_id', 'released_date'
        )
