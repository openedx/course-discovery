# pylint: disable=no-member,test-inherits-tests
import datetime
import itertools
from urllib.parse import urlencode

import ddt
import mock
import pytest
import responses
from django.test import TestCase
from django.utils.text import slugify
from haystack.query import SearchQuerySet
from opaque_keys.edx.keys import CourseKey
from pytz import UTC
from rest_framework.test import APIRequestFactory
from waffle.models import Switch
from waffle.testutils import override_switch

from course_discovery.apps.api.fields import ImageField, StdImageSerializerField
from course_discovery.apps.api.serializers import (
    AffiliateWindowSerializer, CatalogSerializer, ContainedCourseRunsSerializer, ContainedCoursesSerializer,
    ContentTypeSerializer, CorporateEndorsementSerializer, CourseEntitlementSerializer, CourseRunSearchModelSerializer,
    CourseRunSearchSerializer, CourseRunSerializer, CourseRunWithProgramsSerializer, CourseSearchModelSerializer,
    CourseSearchSerializer, CourseSerializer, CourseWithProgramsSerializer, EndorsementSerializer, FAQSerializer,
    FlattenedCourseRunWithCourseSerializer, ImageSerializer, MinimalCourseRunSerializer, MinimalCourseSerializer,
    MinimalOrganizationSerializer, MinimalProgramCourseSerializer, MinimalProgramSerializer, NestedProgramSerializer,
    OrganizationSerializer, PersonSerializer, PositionSerializer, PrerequisiteSerializer, ProgramSearchModelSerializer,
    ProgramSearchSerializer, ProgramSerializer, ProgramTypeSerializer, SubjectSerializer,
    TopicSerializer, TypeaheadCourseRunSearchSerializer, TypeaheadProgramSearchSerializer, VideoSerializer,
    get_utm_source_for_user
)
from course_discovery.apps.api.tests.mixins import SiteMixin
from course_discovery.apps.catalogs.tests.factories import CatalogFactory
from course_discovery.apps.core.models import Partner, User
from course_discovery.apps.core.tests.factories import PartnerFactory, UserFactory
from course_discovery.apps.core.tests.helpers import make_image_file
from course_discovery.apps.core.tests.mixins import ElasticsearchTestMixin, LMSAPIClientMixin
from course_discovery.apps.course_metadata.choices import CourseRunStatus, ProgramStatus
from course_discovery.apps.course_metadata.models import Course, CourseRun, Program
from course_discovery.apps.course_metadata.tests.factories import (
    CorporateEndorsementFactory, CourseFactory, CourseRunFactory, EndorsementFactory, ExpectedLearningItemFactory,
    ImageFactory, JobOutlookItemFactory, OrganizationFactory, PersonFactory, PositionFactory, PrerequisiteFactory,
    ProgramFactory, ProgramTypeFactory, SeatFactory, SeatTypeFactory, SubjectFactory, TopicFactory, VideoFactory
)
from course_discovery.apps.ietf_language_tags.models import LanguageTag


def json_date_format(datetime_obj):
    return datetime.datetime.strftime(datetime_obj, "%Y-%m-%dT%H:%M:%S.%fZ")


def make_request():
    user = UserFactory()
    request = APIRequestFactory().get('/')
    request.user = user
    return request


def serialize_datetime_without_timezone(d):
    # TODO: Remove this function, and replace usage of it with serialize_datetime, after
    # https://github.com/encode/django-rest-framework/issues/3732 is released.
    return d.strftime('%Y-%m-%dT%H:%M:%S') if d else None


def serialize_language(language):
    if language.code.startswith('zh'):
        return language.name

    return language.macrolanguage


def serialize_language_to_code(language):
    return language.code


def get_uuids(items):
    return [str(item.uuid) for item in items]


class CatalogSerializerTests(ElasticsearchTestMixin, TestCase):
    def test_data(self):
        user = UserFactory()
        catalog = CatalogFactory(query='*:*', viewers=[user])  # We intentionally use a query for all Courses.
        courses = CourseFactory.create_batch(10)
        serializer = CatalogSerializer(catalog)

        expected = {
            'id': catalog.id,
            'name': catalog.name,
            'query': catalog.query,
            'courses_count': len(courses),
            'viewers': [user.username]
        }
        self.assertDictEqual(serializer.data, expected)

    def test_invalid_data_user_create(self):
        """Verify that users are not created if the serializer data is invalid."""
        username = 'test-user'
        data = {
            'viewers': [username],
            'id': None,
            'name': '',
            'query': '',
        }
        serializer = CatalogSerializer(data=data)
        self.assertFalse(serializer.is_valid())
        self.assertEqual(User.objects.filter(username=username).count(), 0)  # pylint: disable=no-member


class MinimalCourseSerializerTests(SiteMixin, TestCase):
    serializer_class = MinimalCourseSerializer

    @classmethod
    def get_expected_data(cls, course, request):
        context = {'request': request}

        return {
            'key': course.key,
            'uuid': str(course.uuid),
            'title': course.title,
            'course_runs': MinimalCourseRunSerializer(course.course_runs, many=True, context=context).data,
        }

    def test_data(self):
        request = make_request()
        organizations = OrganizationFactory(partner=self.partner)
        course = CourseFactory(authoring_organizations=[organizations], partner=self.partner)
        CourseRunFactory.create_batch(2, course=course)
        serializer = self.serializer_class(course, context={'request': request})
        expected = self.get_expected_data(course, request)
        self.assertDictEqual(serializer.data, expected)


class CourseSerializerTests(MinimalCourseSerializerTests):
    serializer_class = CourseSerializer

    @classmethod
    def get_expected_data(cls, course, request):
        expected = super().get_expected_data(course, request)
        expected.update({
            'modified': json_date_format(course.modified),  # pylint: disable=no-member
            'course_runs': CourseRunSerializer(course.course_runs, many=True, context={'request': request}).data,
            'card_image_url': course.card_image_url,
        })

        return expected


@ddt.ddt
class CourseWithProgramsSerializerTests(CourseSerializerTests):
    serializer_class = CourseWithProgramsSerializer

    @classmethod
    def get_expected_data(cls, course, request):
        expected = super().get_expected_data(course, request)
        expected.update({
            'programs': NestedProgramSerializer(
                course.programs,
                many=True,
                context={'request': request}
            ).data,
        })

        return expected

    def setUp(self):
        super().setUp()
        self.request = make_request()
        self.course = CourseFactory(partner=self.partner)
        self.deleted_program = ProgramFactory(
            courses=[self.course],
            partner=self.partner,
            status=ProgramStatus.Deleted
        )

    def test_exclude_deleted_programs(self):
        """
        If the associated program is deleted,
        CourseWithProgramsSerializer should not return any serialized programs
        """
        serializer = self.serializer_class(self.course, context={'request': self.request})
        self.assertEqual(serializer.data['programs'], [])

    def test_include_deleted_programs(self):
        """
        If the associated program is deleted, but we are sending in the 'include_deleted_programs' flag
        CourseWithProgramsSerializer should return deleted programs
        """
        serializer = self.serializer_class(
            self.course,
            context={'request': self.request, 'include_deleted_programs': 1}
        )
        self.assertEqual(serializer.data, self.get_expected_data(self.course, self.request))


class MinimalCourseRunSerializerTests(TestCase):
    serializer_class = MinimalCourseRunSerializer

    @classmethod
    def get_expected_data(cls, course_run, request):  # pylint: disable=unused-argument
        return {
            'key': course_run.key,
            'uuid': str(course_run.uuid),
            'title': course_run.title,
            'start': json_date_format(course_run.start),
            'end': json_date_format(course_run.end),
            'enrollment_start': json_date_format(course_run.enrollment_start),
            'enrollment_end': json_date_format(course_run.enrollment_end),
            'pacing_type': course_run.pacing_type,
            'type': course_run.type,
            'status': course_run.status,
        }

    def test_data(self):
        request = make_request()
        course_run = CourseRunFactory()
        serializer = self.serializer_class(course_run, context={'request': request})
        expected = self.get_expected_data(course_run, request)
        self.assertDictEqual(serializer.data, expected)


class CourseRunSerializerTests(MinimalCourseRunSerializerTests):
    serializer_class = CourseRunSerializer

    @classmethod
    def get_expected_data(cls, course_run, request):
        expected = super().get_expected_data(course_run, request)
        expected.update({
            'course': course_run.course.key,
            'key': course_run.key,
            'title': course_run.title,  # pylint: disable=no-member
            'content_language': course_run.language.code,
            'instructors': [],
            'modified': json_date_format(course_run.modified),  # pylint: disable=no-member
            'availability': course_run.availability,
            'status': course_run.status,
        })

        return expected


class CourseRunWithProgramsSerializerTests(TestCase):
    def setUp(self):
        super().setUp()
        self.request = make_request()
        self.course_run = CourseRunFactory()
        self.serializer_context = {'request': self.request}

    def test_data(self):
        serializer = CourseRunWithProgramsSerializer(self.course_run, context=self.serializer_context)
        ProgramFactory(courses=[self.course_run.course])
        self.assertDictEqual(serializer.data, self.get_expected_data(self.course_run, self.request))

    def test_data_excluded_course_run(self):
        """
        If a course run is excluded on a program, that program should not be
        returned for that course run on the course run endpoint.
        """
        serializer = CourseRunWithProgramsSerializer(self.course_run, context=self.serializer_context)
        ProgramFactory(courses=[self.course_run.course], excluded_course_runs=[self.course_run])
        expected = CourseRunSerializer(self.course_run, context=self.serializer_context).data
        expected.update({'programs': []})
        assert serializer.data == expected

    def test_exclude_deleted_programs(self):
        """
        If the associated program is deleted,
        CourseRunWithProgramsSerializer should not return any serialized programs
        """
        ProgramFactory(courses=[self.course_run.course], status=ProgramStatus.Deleted)
        serializer = CourseRunWithProgramsSerializer(self.course_run, context=self.serializer_context)
        self.assertEqual(serializer.data['programs'], [])

    def test_include_deleted_programs(self):
        """
        If the associated program is deleted, but we are sending in the 'include_deleted_programs' flag
        CourseRunWithProgramsSerializer should return deleted programs
        """
        deleted_program = ProgramFactory(courses=[self.course_run.course], status=ProgramStatus.Deleted)
        self.serializer_context['include_deleted_programs'] = 1
        serializer = CourseRunWithProgramsSerializer(self.course_run, context=self.serializer_context)
        self.assertEqual(
            serializer.data['programs'],
            NestedProgramSerializer([deleted_program], many=True, context=self.serializer_context).data
        )

    def test_exclude_unpublished_program(self):
        """
        If a program is unpublished, that program should not be returned on the course run endpoint by default.
        """
        ProgramFactory(courses=[self.course_run.course], status=ProgramStatus.Unpublished)
        serializer = CourseRunWithProgramsSerializer(self.course_run, context=self.serializer_context)
        self.assertEqual(serializer.data['programs'], [])

    def test_include_unpublished_programs(self):
        """
        If a program is unpublished, that program should only be returned on the course run endpoint if we are
        sending the 'include_unpublished_programs' flag.
        """
        unpublished_program = ProgramFactory(courses=[self.course_run.course], status=ProgramStatus.Unpublished)
        self.serializer_context['include_unpublished_programs'] = 1
        serializer = CourseRunWithProgramsSerializer(self.course_run, context=self.serializer_context)
        self.assertEqual(
            serializer.data['programs'],
            NestedProgramSerializer([unpublished_program], many=True, context=self.serializer_context).data
        )

    def test_exclude_retired_program(self):
        """
        If a program is retired, that program should not be returned on the course run endpoint by default.
        """
        ProgramFactory(courses=[self.course_run.course], status=ProgramStatus.Retired)
        serializer = CourseRunWithProgramsSerializer(self.course_run, context=self.serializer_context)
        self.assertEqual(serializer.data['programs'], [])

    def test_include_retired_programs(self):
        """
        If a program is retired, that program should only be returned on the course run endpoint if we are
        sending the 'include_retired_programs' flag.
        """
        retired_program = ProgramFactory(courses=[self.course_run.course], status=ProgramStatus.Retired)
        self.serializer_context['include_retired_programs'] = 1
        serializer = CourseRunWithProgramsSerializer(self.course_run, context=self.serializer_context)
        self.assertEqual(
            serializer.data['programs'],
            NestedProgramSerializer([retired_program], many=True, context=self.serializer_context).data
        )

    @classmethod
    def get_expected_data(cls, course_run, request):
        expected = CourseRunSerializer(course_run, context={'request': request}).data
        expected.update({
            'programs': NestedProgramSerializer(
                course_run.course.programs,
                many=True,
                context={'request': request},
            ).data,
        })
        return expected


class MinimalProgramCourseSerializerTests(TestCase):
    def setUp(self):
        super(MinimalProgramCourseSerializerTests, self).setUp()
        self.program = ProgramFactory(courses=[CourseFactory()])

    def assert_program_courses_serialized(self, program):
        request = make_request()

        serializer = MinimalProgramCourseSerializer(
            program.courses,
            many=True,
            context={
                'request': request,
                'program': program,
                'course_runs': list(program.course_runs)
            }
        )
        expected = MinimalCourseSerializer(program.courses, many=True, context={'request': request}).data
        self.assertSequenceEqual(serializer.data, expected)

    def test_data(self):
        for course in self.program.courses.all():
            CourseRunFactory(course=course)

        self.assert_program_courses_serialized(self.program)

    def test_data_without_course_runs(self):
        """
        Make sure that if a course has no runs, the serializer still works as expected
        """
        self.assert_program_courses_serialized(self.program)

    def test_with_exclusions(self):
        """
        Test serializer with course_run exclusions within program
        """
        request = make_request()
        course = CourseFactory()
        excluded_runs = []
        course_runs = CourseRunFactory.create_batch(2, course=course)
        excluded_runs.append(course_runs[0])
        program = ProgramFactory(courses=[course], excluded_course_runs=excluded_runs)

        serializer_context = {'request': request, 'program': program, 'course_runs': list(program.course_runs)}
        serializer = MinimalProgramCourseSerializer(course, context=serializer_context)

        expected = MinimalCourseSerializer(course, context=serializer_context).data
        expected['course_runs'] = MinimalCourseRunSerializer(
            [course_runs[1]], many=True, context={'request': request}).data
        self.assertDictEqual(serializer.data, expected)

    def test_with_published_course_runs_only_context(self):
        """ Verify setting the published_course_runs_only context value excludes unpublished course runs. """
        # Create a program and course. The course should have both published and un-published course runs.
        request = make_request()
        course = CourseFactory()
        program = ProgramFactory(courses=[course])
        unpublished_course_run = CourseRunFactory(status=CourseRunStatus.Unpublished, course=course)
        CourseRunFactory(status=CourseRunStatus.Published, course=course)

        # We do NOT expect the results to included the unpublished data
        expected = MinimalCourseSerializer(course, context={'request': request}).data
        expected['course_runs'] = [course_run for course_run in expected['course_runs'] if
                                   course_run['key'] != str(unpublished_course_run.key)]
        self.assertEqual(len(expected['course_runs']), 1)

        serializer = MinimalProgramCourseSerializer(
            course,
            context={
                'request': request,
                'program': program,
                'published_course_runs_only': True,
                'course_runs': list(program.course_runs),
            }
        )

        self.assertSequenceEqual(serializer.data, expected)

    def test_use_full_course_serializer(self):
        """
        Verify that we can use the `use_full_course_serializer` parameter to use the
        CourseRun serializer.
        """
        request = make_request()
        course = CourseFactory()
        program = ProgramFactory(courses=[course])
        CourseRunFactory(course=course)

        serializer_data = MinimalProgramCourseSerializer(
            course,
            context={
                'request': request,
                'program': program,
                'use_full_course_serializer': 1,
                'course_runs': list(program.course_runs),
            }
        ).data

        expected = CourseRunSerializer(
            course.course_runs.all(),
            many=True,
            context={
                'request': request,
                'use_full_course_serializer': 1
            }
        ).data

        assert serializer_data['course_runs'] == expected


class MinimalProgramSerializerTests(TestCase):
    serializer_class = MinimalProgramSerializer

    def create_program(self):
        organizations = OrganizationFactory.create_batch(2)
        person = PersonFactory()

        courses = CourseFactory.create_batch(3)
        for course in courses:
            CourseRunFactory.create_batch(2, course=course, start=datetime.datetime.now(UTC))

        return ProgramFactory(
            courses=courses,
            authoring_organizations=organizations,
            credit_backing_organizations=organizations,
            corporate_endorsements=CorporateEndorsementFactory.create_batch(1),
            individual_endorsements=EndorsementFactory.create_batch(1),
            expected_learning_items=ExpectedLearningItemFactory.create_batch(1),
            job_outlook_items=JobOutlookItemFactory.create_batch(1),
            banner_image=make_image_file('test_banner.jpg'),
            video=VideoFactory(),
            order_courses_by_start_date=False,
        )

    @classmethod
    def get_expected_data(cls, program, request):
        image_field = StdImageSerializerField()
        image_field._context = {'request': request}  # pylint: disable=protected-access

        return {
            'uuid': str(program.uuid),
            'title': program.title,
            'subtitle': program.subtitle,
            'type': program.type.name,
            'status': program.status,
            'marketing_slug': program.marketing_slug,
            'marketing_url': program.marketing_url,
            'banner_image': image_field.to_representation(program.banner_image),
            'hidden': program.hidden,
            'courses': MinimalProgramCourseSerializer(
                program.courses,
                many=True,
                context={
                    'request': request,
                    'program': program,
                    'course_runs': list(program.course_runs),
                }).data,
            'authoring_organizations': MinimalOrganizationSerializer(program.authoring_organizations, many=True).data,
            'card_image_url': program.card_image_url,
            'is_program_eligible_for_one_click_purchase': program.is_program_eligible_for_one_click_purchase
        }

    def test_data(self):
        request = make_request()
        program = self.create_program()
        serializer = self.serializer_class(program, context={'request': request})
        expected = self.get_expected_data(program, request)
        self.assertDictEqual(serializer.data, expected)


class ProgramSerializerTests(MinimalProgramSerializerTests):
    serializer_class = ProgramSerializer

    @classmethod
    def get_expected_data(cls, program, request):
        expected = super().get_expected_data(program, request)
        expected.update({
            'authoring_organizations': OrganizationSerializer(program.authoring_organizations, many=True).data,
            'video': VideoSerializer(program.video).data,
            'credit_redemption_overview': program.credit_redemption_overview,
            'applicable_seat_types': list(program.type.applicable_seat_types.values_list('slug', flat=True)),
            'corporate_endorsements': CorporateEndorsementSerializer(program.corporate_endorsements, many=True).data,
            'credit_backing_organizations': OrganizationSerializer(
                program.credit_backing_organizations,
                many=True
            ).data,
            'expected_learning_items': [item.value for item in program.expected_learning_items.all()],
            'faq': FAQSerializer(program.faq, many=True).data,
            'individual_endorsements': EndorsementSerializer(
                program.individual_endorsements, many=True, context={'request': request}
            ).data,
            'instructor_ordering': PersonSerializer(
                program.instructor_ordering,
                many=True,
                context={'request': request}
            ).data,
            'job_outlook_items': [item.value for item in program.job_outlook_items.all()],
            'languages': [serialize_language_to_code(l) for l in program.languages],
            'weeks_to_complete': program.weeks_to_complete,
            'total_hours_of_effort': program.total_hours_of_effort,
            'max_hours_effort_per_week': program.max_hours_effort_per_week,
            'min_hours_effort_per_week': program.min_hours_effort_per_week,
            'overview': program.overview
        })
        return expected

    def test_data_with_exclusions(self):
        """
        Verify we can specify program excluded_course_runs and the serializers will
        render the course_runs with exclusions
        """
        request = make_request()
        program = self.create_program()

        excluded_course_run = program.courses.all()[0].course_runs.all()[0]
        program.excluded_course_runs.add(excluded_course_run)

        expected = self.get_expected_data(program, request)
        serializer = self.serializer_class(program, context={'request': request})
        self.assertDictEqual(serializer.data, expected)

    def test_course_ordering(self):
        """
        Verify that courses in a program are ordered by ascending run start date,
        with ties broken by earliest run enrollment start date.
        """
        request = make_request()
        course_list = CourseFactory.create_batch(3)

        # Create a course run with arbitrary start and empty enrollment_start.
        CourseRunFactory(
            course=course_list[2],
            enrollment_start=None,
            start=datetime.datetime(2014, 2, 1, tzinfo=UTC),
        )

        # Create a second run with matching start, but later enrollment_start.
        CourseRunFactory(
            course=course_list[1],
            enrollment_start=datetime.datetime(2014, 1, 2),
            start=datetime.datetime(2014, 2, 1, tzinfo=UTC),
        )

        # Create a third run with later start and enrollment_start.
        CourseRunFactory(
            course=course_list[0],
            enrollment_start=datetime.datetime(2014, 2, 1, tzinfo=UTC),
            start=datetime.datetime(2014, 3, 1, tzinfo=UTC),
        )

        program = ProgramFactory(courses=course_list)
        serializer = self.serializer_class(program, context={'request': request})

        expected = MinimalProgramCourseSerializer(
            # The expected ordering is the reverse of course_list.
            course_list[::-1],
            many=True,
            context={'request': request, 'program': program, 'course_runs': list(program.course_runs)}
        ).data

        self.assertEqual(serializer.data['courses'], expected)

    def test_course_ordering_with_exclusions(self):
        """
        Verify that excluded course runs aren't used when ordering courses.
        """
        request = make_request()
        course_list = CourseFactory.create_batch(3)

        # Create a course run with arbitrary start and empty enrollment_start.
        # This run will be excluded from the program. If it wasn't excluded,
        # the expected course ordering, by index, would be: 0, 2, 1.
        excluded_run = CourseRunFactory(
            course=course_list[0],
            enrollment_start=None,
            start=datetime.datetime(2014, 1, 1, tzinfo=UTC),
        )

        # Create a run with later start and empty enrollment_start.
        CourseRunFactory(
            course=course_list[2],
            enrollment_start=None,
            start=datetime.datetime(2014, 2, 1, tzinfo=UTC),
        )

        # Create a run with matching start, but later enrollment_start.
        CourseRunFactory(
            course=course_list[1],
            enrollment_start=datetime.datetime(2014, 1, 2),
            start=datetime.datetime(2014, 2, 1, tzinfo=UTC),
        )

        # Create a run with later start and enrollment_start.
        CourseRunFactory(
            course=course_list[0],
            enrollment_start=datetime.datetime(2014, 2, 1, tzinfo=UTC),
            start=datetime.datetime(2014, 3, 1, tzinfo=UTC),
        )

        program = ProgramFactory(courses=course_list, excluded_course_runs=[excluded_run])
        serializer = self.serializer_class(program, context={'request': request})

        expected = MinimalProgramCourseSerializer(
            # The expected ordering is the reverse of course_list.
            course_list[::-1],
            many=True,
            context={'request': request, 'program': program, 'course_runs': list(program.course_runs)}
        ).data

        self.assertEqual(serializer.data['courses'], expected)

    def test_course_ordering_with_no_start(self):
        """
        Verify that a courses run with missing start date appears last when ordering courses.
        """
        request = make_request()
        course_list = CourseFactory.create_batch(3)

        # Create a course run with arbitrary start and empty enrollment_start.
        CourseRunFactory(
            course=course_list[2],
            enrollment_start=None,
            start=datetime.datetime(2014, 2, 1, tzinfo=UTC),
        )

        # Create a second run with matching start, but later enrollment_start.
        CourseRunFactory(
            course=course_list[1],
            enrollment_start=datetime.datetime(2014, 1, 2),
            start=datetime.datetime(2014, 2, 1, tzinfo=UTC),
        )

        # Create a third run with empty start and enrollment_start.
        CourseRunFactory(
            course=course_list[0],
            enrollment_start=None,
            start=None,
        )

        program = ProgramFactory(courses=course_list)
        serializer = self.serializer_class(program, context={'request': request})

        expected = MinimalProgramCourseSerializer(
            # The expected ordering is the reverse of course_list.
            course_list[::-1],
            many=True,
            context={'request': request, 'program': program, 'course_runs': list(program.course_runs)}
        ).data

        self.assertEqual(serializer.data['courses'], expected)

    def test_data_without_course_sorting(self):
        request = make_request()

        program = self.create_program()
        program.order_courses_by_start_date = False
        program.save()

        serializer = self.serializer_class(program, context={'request': request})
        expected = self.get_expected_data(program, request)
        self.assertDictEqual(serializer.data, expected)

    def test_marketable_enrollable_course_runs_with_archived(self):
        """ Test that the marketable_enrollable_course_runs_with_archived flag hides course runs
        that are not marketable or enrollable
        """
        course = CourseFactory()
        CourseRunFactory(status=CourseRunStatus.Unpublished, course=course)
        marketable_enrollable_run = CourseRunFactory(
            status=CourseRunStatus.Published,
            end=datetime.datetime.now(UTC) + datetime.timedelta(days=10),
            enrollment_start=None,
            enrollment_end=None,
            course=course
        )
        SeatFactory(course_run=marketable_enrollable_run)
        program = ProgramFactory(courses=[course])
        request = make_request()

        serializer = self.serializer_class(
            program,
            context={
                'request': request,
                'marketable_enrollable_course_runs_with_archived': True
            }
        )

        expected = MinimalProgramCourseSerializer(
            [course],
            many=True,
            context={
                'request': request,
                'program': program,
                'course_runs': [marketable_enrollable_run]
            }
        ).data

        assert len(expected[0]['course_runs']) == 1
        assert sorted(serializer.data['courses'][0]['course_runs'], key=lambda x: x['key']) == \
            sorted(expected[0]['course_runs'], key=lambda x: x['key'])


class ProgramTypeSerializerTests(TestCase):
    serializer_class = ProgramTypeSerializer

    @classmethod
    def get_expected_data(cls, program_type, request):
        image_field = StdImageSerializerField()
        image_field._context = {'request': request}  # pylint: disable=protected-access

        return {
            'name': program_type.name,
            'logo_image': image_field.to_representation(program_type.logo_image),
            'applicable_seat_types': [seat_type.slug for seat_type in program_type.applicable_seat_types.all()],
            'slug': program_type.slug,
        }

    def test_data(self):
        request = make_request()
        applicable_seat_types = SeatTypeFactory.create_batch(3)
        program_type = ProgramTypeFactory(applicable_seat_types=applicable_seat_types)
        serializer = self.serializer_class(program_type, context={'request': request})
        expected = self.get_expected_data(program_type, request)
        self.assertDictEqual(serializer.data, expected)


class ContainedCourseRunsSerializerTests(TestCase):
    def test_data(self):
        instance = {
            'course_runs': {
                'course-v1:edX+DemoX+Demo_Course': True,
                'a/b/c': False
            }
        }
        serializer = ContainedCourseRunsSerializer(instance)
        self.assertDictEqual(serializer.data, instance)


class ContainedCoursesSerializerTests(TestCase):
    def test_data(self):
        instance = {
            'courses': {
                'course-v1:edX+DemoX+Demo_Course': True,
                'a/b/c': False
            }
        }
        serializer = ContainedCoursesSerializer(instance)
        self.assertDictEqual(serializer.data, instance)


@ddt.ddt
class ContentTypeSerializerTests(TestCase):
    @ddt.data(
        (CourseFactory, 'course'),
        (CourseRunFactory, 'courserun'),
        (ProgramFactory, 'program'),
    )
    @ddt.unpack
    def test_data(self, factory_class, expected_content_type):
        obj = factory_class()
        serializer = ContentTypeSerializer(obj)
        expected = {
            'content_type': expected_content_type
        }
        assert serializer.data == expected


@ddt.ddt
class NamedModelSerializerTests(TestCase):
    @ddt.data(
        (PrerequisiteFactory, PrerequisiteSerializer),
    )
    @ddt.unpack
    def test_data(self, factory_class, serializer_class):
        link_object = factory_class()
        serializer = serializer_class(link_object)

        expected = {
            'name': link_object.name
        }

        self.assertDictEqual(serializer.data, expected)


class SubjectSerializerTests(TestCase):
    def test_data(self):
        subject = SubjectFactory()
        serializer = SubjectSerializer(subject)

        expected = {
            'name': subject.name,
            'description': subject.description,
            'banner_image_url': subject.banner_image_url,
            'card_image_url': subject.card_image_url,
            'subtitle': subject.subtitle,
            'slug': subject.slug,
            'uuid': str(subject.uuid),
        }

        self.assertDictEqual(serializer.data, expected)


class TopicSerializerTests(TestCase):
    def test_data(self):
        topic = TopicFactory()
        serializer = TopicSerializer(topic)

        expected = {
            'name': topic.name,
            'description': topic.description,
            'long_description': topic.long_description,
            'banner_image_url': topic.banner_image_url,
            'subtitle': topic.subtitle,
            'slug': topic.slug,
            'uuid': str(topic.uuid),
        }

        self.assertDictEqual(serializer.data, expected)


class ImageSerializerTests(TestCase):
    def test_data(self):
        image = ImageFactory()
        serializer = ImageSerializer(image)

        expected = {
            'src': image.src,
            'description': image.description,
            'height': image.height,
            'width': image.width
        }

        self.assertDictEqual(serializer.data, expected)


class CorporateEndorsementSerializerTests(TestCase):
    def test_data(self):
        corporate_endorsement = CorporateEndorsementFactory()
        serializer = CorporateEndorsementSerializer(corporate_endorsement)

        expected = {
            'corporation_name': corporate_endorsement.corporation_name,
            'statement': corporate_endorsement.statement,
            'image': ImageSerializer(corporate_endorsement.image).data,
            'individual_endorsements': EndorsementSerializer(
                corporate_endorsement.individual_endorsements,
                many=True
            ).data
        }

        self.assertDictEqual(serializer.data, expected)


class NestedProgramSerializerTests(TestCase):
    def test_data(self):
        program = ProgramFactory()
        serializer = NestedProgramSerializer(program)

        expected = {
            'uuid': str(program.uuid),
            'marketing_slug': program.marketing_slug,
            'marketing_url': program.marketing_url,  # pylint: disable=no-member
            'type': program.type.name,
            'title': program.title,
        }

        self.assertDictEqual(serializer.data, expected)


class VideoSerializerTests(TestCase):
    def test_data(self):
        video = VideoFactory()
        image = video.image
        serializer = VideoSerializer(video)

        expected = {
            'src': video.src,
            'description': video.description,
            'image': ImageSerializer(image).data
        }

        self.assertDictEqual(serializer.data, expected)


class MinimalOrganizationSerializerTests(TestCase):
    serializer_class = MinimalOrganizationSerializer

    def create_organization(self):
        return OrganizationFactory()

    @classmethod
    def get_expected_data(cls, organization):
        return {
            'uuid': str(organization.uuid),
            'key': organization.key,
            'name': organization.name,
        }

    def test_data(self):
        organization = self.create_organization()
        serializer = self.serializer_class(organization)
        expected = self.get_expected_data(organization)
        self.assertDictEqual(serializer.data, expected)


class OrganizationSerializerTests(MinimalOrganizationSerializerTests):
    TAG = 'test-tag'
    serializer_class = OrganizationSerializer

    def create_organization(self):
        organization = super().create_organization()
        organization.tags.add(self.TAG)
        return organization

    @classmethod
    def get_expected_data(cls, organization):
        expected = super().get_expected_data(organization)
        expected.update({
            'certificate_logo_image_url': organization.certificate_logo_image_url,
            'description': organization.description,
            'homepage_url': organization.homepage_url,
            'logo_image_url': organization.logo_image_url,
            'tags': [cls.TAG],
            'marketing_url': organization.marketing_url,
        })

        return expected


class PersonSerializerTests(TestCase):
    def setUp(self):
        request = make_request()
        self.context = {'request': request}
        image_field = StdImageSerializerField()
        image_field._context = self.context  # pylint: disable=protected-access

        position = PositionFactory()
        self.person = position.person
        self.person.salutation = 'Dr.'
        self.expected = {
            'uuid': str(self.person.uuid),
            'salutation': self.person.salutation,
            'given_name': self.person.given_name,
            'family_name': self.person.family_name,
            'bio': self.person.bio,
            'profile_image': image_field.to_representation(self.person.profile_image),
            'profile_image_url': self.person.profile_image.url,
            'position': PositionSerializer(position).data,
            'works': [work.value for work in self.person.person_works.all()],
            'urls': {
                'facebook': None,
                'twitter': None,
                'blog': None
            },
            'slug': self.person.slug,
            'email': self.person.email,
        }

    def test_data(self):
        serializer = PersonSerializer(self.person, context=self.context)
        self.assertDictEqual(serializer.data, self.expected)

    def test_profile_image_url_override(self):
        self.person.profile_image_url = None
        self.expected['profile_image_url'] = self.person.profile_image.url
        serializer = PersonSerializer(self.person, context=self.context)
        self.assertDictEqual(serializer.data, self.expected)


class PositionSerializerTests(TestCase):
    def test_data(self):
        position = PositionFactory()
        serializer = PositionSerializer(position)
        expected = {
            'title': str(position.title),
            'organization_name': position.organization_name,
            'organization_id': position.organization_id,
            'organization_override': position.organization_override
        }

        self.assertDictEqual(serializer.data, expected)


class AffiliateWindowSerializerTests(TestCase):
    def test_data(self):
        user = UserFactory()
        CatalogFactory(query='*:*', viewers=[user])
        course_run = CourseRunFactory()
        seat = SeatFactory(course_run=course_run)
        serializer = AffiliateWindowSerializer(seat)

        # Verify none of the course run attributes are empty; otherwise, Affiliate Window will report errors.
        # pylint: disable=no-member
        assert all((course_run.title,))

        expected = {
            'pid': '{}-{}'.format(course_run.key, seat.type),
            'name': course_run.title,
            'price': {
                'actualp': seat.price
            },
            'currency': seat.currency.code,
            'imgurl': course_run.card_image_url,
            'category': 'Other Experiences',
            'validfrom': course_run.start.strftime('%Y-%m-%d'),
            'validto': course_run.end.strftime('%Y-%m-%d'),
            'lang': course_run.language.code.split('-')[0].upper(),
            'custom1': course_run.pacing_type,
            'custom2': course_run.level_type.name,
            'custom3': ','.join(subject.name for subject in course_run.subjects.all()),
            'custom4': ','.join(org.name for org in course_run.authoring_organizations.all()),
        }

        assert serializer.data == expected


class CourseSearchSerializerTests(TestCase):
    serializer_class = CourseSearchSerializer

    def test_data(self):
        request = make_request()
        course = CourseFactory()
        serializer = self.serialize_course(course, request)
        assert serializer.data == self.get_expected_data(course, request)

    def serialize_course(self, course, request):
        """ Serializes the given `Course` as a search result. """
        result = SearchQuerySet().models(Course).filter(key=course.key)[0]
        serializer = self.serializer_class(result, context={'request': request})
        return serializer

    @classmethod
    def get_expected_data(cls, course, request):  # pylint: disable=unused-argument
        return {
            'key': course.key,
            'title': course.title,
            'short_description': course.short_description,
            'full_description': course.full_description,
            'content_type': 'course',
            'aggregation_key': 'course:{}'.format(course.key),
            'card_image_url': course.card_image_url,
        }


class CourseSearchModelSerializerTests(CourseSearchSerializerTests):
    serializer_class = CourseSearchModelSerializer

    @classmethod
    def get_expected_data(cls, course, request):
        expected_data = CourseWithProgramsSerializerTests.get_expected_data(course, request)
        expected_data.update({'content_type': 'course'})
        return expected_data


class CourseRunSearchSerializerTests(ElasticsearchTestMixin, TestCase):
    serializer_class = CourseRunSearchSerializer

    def test_data(self):
        request = make_request()
        course_run = CourseRunFactory()
        SeatFactory.create(course_run=course_run, type='verified', price=10, sku='ABCDEF')
        program = ProgramFactory(courses=[course_run.course])
        self.reindex_courses(program)
        serializer = self.serialize_course_run(course_run, request)
        assert serializer.data == self.get_expected_data(course_run, request)

    def test_data_without_serializers(self):
        """ Verify a null `LevelType` is properly serialized as None. """
        request = make_request()
        course_run = CourseRunFactory(course__level_type=None)
        serializer = self.serialize_course_run(course_run, request)
        assert serializer.data['level_type'] is None

    def serialize_course_run(self, course_run, request):
        """ Serializes the given `CourseRun` as a search result. """
        result = SearchQuerySet().models(CourseRun).filter(key=course_run.key)[0]
        serializer = self.serializer_class(result, context={'request': request})
        return serializer

    @classmethod
    def get_expected_data(cls, course_run, request):  # pylint: disable=unused-argument
        return {
            'start': serialize_datetime_without_timezone(course_run.start),
            'end': serialize_datetime_without_timezone(course_run.end),
            'enrollment_start': serialize_datetime_without_timezone(course_run.enrollment_start),
            'enrollment_end': serialize_datetime_without_timezone(course_run.enrollment_end),
            'key': course_run.key,
            'pacing_type': course_run.pacing_type,
            'language': serialize_language(course_run.language),
            'title': course_run.title,
            'content_type': 'courserun',
            'org': CourseKey.from_string(course_run.key).org,
            'number': CourseKey.from_string(course_run.key).course,
            'type': course_run.type,
            'availability': course_run.availability,
            'published': course_run.status == CourseRunStatus.Published,
            'partner': course_run.course.partner.short_code,
            'aggregation_key': 'courserun:{}'.format(course_run.course.key),
        }


class CourseRunSearchModelSerializerTests(CourseRunSearchSerializerTests):
    serializer_class = CourseRunSearchModelSerializer

    @classmethod
    def get_expected_data(cls, course_run, request):
        expected_data = CourseRunWithProgramsSerializerTests.get_expected_data(course_run, request)
        expected_data.update({'content_type': 'courserun'})
        # This explicit conversion needs to happen, apparently because the real type is DRF's 'ReturnDict'. It's weird.
        return dict(expected_data)


@pytest.mark.django_db
@pytest.mark.usefixtures('haystack_default_connection')
class TestProgramSearchSerializer(TestCase):
    serializer_class = ProgramSearchSerializer

    def setUp(self):
        super().setUp()
        self.request = make_request()

    @classmethod
    def get_expected_data(cls, program, request):  # pylint: disable=unused-argument
        return {
            'uuid': str(program.uuid),
            'title': program.title,
            'subtitle': program.subtitle,
            'type': program.type.name,
            'marketing_url': program.marketing_url,
            'authoring_organizations': OrganizationSerializer(program.authoring_organizations, many=True).data,
            'content_type': 'program',
            'card_image_url': program.card_image_url,
            'status': program.status,
            'published': program.status == ProgramStatus.Active,
            'partner': program.partner.short_code,
            'authoring_organization_uuids': get_uuids(program.authoring_organizations.all()),
            'aggregation_key': 'program:{}'.format(program.uuid),
            'min_hours_effort_per_week': program.min_hours_effort_per_week,
            'max_hours_effort_per_week': program.max_hours_effort_per_week,
            'language': [serialize_language(language) for language in program.languages],
            'hidden': program.hidden,
            'is_program_eligible_for_one_click_purchase': program.is_program_eligible_for_one_click_purchase
        }

    def serialize_program(self, program, request):
        """ Serializes the given `Program` as a search result. """
        result = SearchQuerySet().models(Program).filter(uuid=program.uuid)[0]
        serializer = self.serializer_class(result, context={'request': request})
        return serializer

    def test_data(self):
        authoring_organization, crediting_organization = OrganizationFactory.create_batch(2)
        program = ProgramFactory(authoring_organizations=[authoring_organization],
                                 credit_backing_organizations=[crediting_organization])
        serializer = self.serialize_program(program, self.request)
        expected = self.get_expected_data(program, self.request)
        assert serializer.data == expected

    def test_data_without_organizations(self):
        """ Verify the serializer serialized programs with no associated organizations.
        In such cases the organizations value should be an empty array. """
        program = ProgramFactory(authoring_organizations=[], credit_backing_organizations=[])
        serializer = self.serialize_program(program, self.request)
        expected = self.get_expected_data(program, self.request)
        assert serializer.data == expected

    def test_data_with_languages(self):
        """
        Verify that program languages are serialized.
        """
        course_run = CourseRunFactory(language=LanguageTag.objects.get(code='en-us'),
                                      authoring_organizations=[OrganizationFactory()])
        CourseRunFactory(course=course_run.course, language=LanguageTag.objects.get(code='zh-cmn'))
        program = ProgramFactory(courses=[course_run.course])
        serializer = self.serialize_program(program, self.request)
        expected = self.get_expected_data(program, self.request)
        assert serializer.data == expected
        if 'language' in expected:
            assert {'English', 'Chinese - Mandarin'} == {*expected['language']}
        else:
            assert {'en-us', 'zh-cmn'} == {*expected['languages']}


class ProgramSearchModelSerializerTest(TestProgramSearchSerializer):
    serializer_class = ProgramSearchModelSerializer

    @classmethod
    def get_expected_data(cls, program, request):
        expected = ProgramSerializerTests.get_expected_data(program, request)
        expected.update({'content_type': 'program'})
        return expected


@pytest.mark.django_db
@pytest.mark.usefixtures('haystack_default_connection')
class TestTypeaheadCourseRunSearchSerializer:
    serializer_class = TypeaheadCourseRunSearchSerializer

    @classmethod
    def get_expected_data(cls, course_run):
        return {
            'key': course_run.key,
            'title': course_run.title,
        }

    def test_data(self):
        authoring_organization = OrganizationFactory()
        course_run = CourseRunFactory(authoring_organizations=[authoring_organization])
        serialized_course = self.serialize_course_run(course_run)
        assert serialized_course.data == self.get_expected_data(course_run)

    def serialize_course_run(self, course_run):
        """ Serializes the given `CourseRun` as a typeahead result. """
        result = SearchQuerySet().models(CourseRun).filter(key=course_run.key)[0]
        serializer = self.serializer_class(result)
        return serializer


@pytest.mark.django_db
@pytest.mark.usefixtures('haystack_default_connection')
class TestTypeaheadProgramSearchSerializer:
    serializer_class = TypeaheadProgramSearchSerializer

    @classmethod
    def get_expected_data(cls, program):
        return {
            'uuid': str(program.uuid),
            'title': program.title,
            'type': program.type.name,
            'orgs': [org.key for org in program.authoring_organizations.all()],
            'marketing_url': program.marketing_url,
        }

    def test_data(self):
        authoring_organization = OrganizationFactory()
        program = ProgramFactory(authoring_organizations=[authoring_organization])
        serialized_program = self.serialize_program(program)
        expected = self.get_expected_data(program)
        assert serialized_program.data == expected

    def test_data_multiple_authoring_organizations(self):
        authoring_organizations = OrganizationFactory.create_batch(3)
        program = ProgramFactory(authoring_organizations=authoring_organizations)
        serialized_program = self.serialize_program(program)
        expected = [org.key for org in authoring_organizations]
        assert serialized_program.data['orgs'] == expected

    def serialize_program(self, program):
        """ Serializes the given `Program` as a typeahead result. """
        result = SearchQuerySet().models(Program).filter(uuid=program.uuid)[0]
        serializer = self.serializer_class(result)
        return serializer


class TestGetUTMSourceForUser(LMSAPIClientMixin, TestCase):

    def setUp(self):
        super(TestGetUTMSourceForUser, self).setUp()

        self.switch, __ = Switch.objects.update_or_create(
            name='use_company_name_as_utm_source_value', defaults={'active': True}
        )
        self.user = UserFactory.create()
        self.partner = PartnerFactory.create()

    @override_switch('use_company_name_as_utm_source_value', active=False)
    @mock.patch.object(Partner, 'access_token', return_value='JWT fake')
    def test_with_waffle_switch_turned_off(self, mock_access_token):  # pylint: disable=unused-argument
        """
        Verify that `get_utm_source_for_user` returns User's username when waffle switch
        `use_company_name_as_utm_source_value` is turned off.
        """

        assert get_utm_source_for_user(self.partner, self.user) == self.user.username

    @mock.patch.object(Partner, 'access_token', return_value='JWT fake')
    def test_with_missing_lms_url(self, mock_access_token):  # pylint: disable=unused-argument
        """
        Verify that `get_utm_source_for_user` returns default value if
        `Partner.lms_url` is not set in the database.
        """
        # Remove lms_url from partner.
        self.partner.lms_url = ''
        self.partner.save()

        assert get_utm_source_for_user(self.partner, self.user) == self.user.username

    @responses.activate
    @mock.patch.object(Partner, 'access_token', return_value='JWT fake')
    def test_when_api_response_is_not_valid(self, mock_access_token):  # pylint: disable=unused-argument
        """
        Verify that `get_utm_source_for_user` returns default value if
        LMS API does not return a valid response.
        """
        self.mock_api_access_request(self.partner.lms_url, self.user, status=400)
        assert get_utm_source_for_user(self.partner, self.user) == self.user.username

    @responses.activate
    @mock.patch.object(Partner, 'access_token', return_value='JWT fake')
    def test_get_utm_source_for_user(self, mock_access_token):  # pylint: disable=unused-argument
        """
        Verify that `get_utm_source_for_user` returns correct value.
        """
        company_name = 'Test Company'
        expected_utm_source = slugify('{} {}'.format(self.user.username, company_name))

        self.mock_api_access_request(
            self.partner.lms_url, self.user, api_access_request_overrides={'company_name': company_name},
        )
        assert get_utm_source_for_user(self.partner, self.user) == expected_utm_source
