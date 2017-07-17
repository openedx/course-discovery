# pylint: disable=no-member, test-inherits-tests
import datetime
import itertools
from urllib.parse import urlencode

import ddt
import pytz
from django.test import TestCase
from haystack.query import SearchQuerySet
from opaque_keys.edx.keys import CourseKey
from rest_framework.test import APIRequestFactory

from course_discovery.apps.api.fields import ImageField, StdImageSerializerField
from course_discovery.apps.api.serializers import (
    AffiliateWindowSerializer, CatalogSerializer, ContainedCourseRunsSerializer, ContainedCoursesSerializer,
    CorporateEndorsementSerializer, CourseRunSearchSerializer, CourseRunSerializer, CourseRunWithProgramsSerializer,
    CourseSearchSerializer, CourseSerializer, CourseWithProgramsSerializer, EndorsementSerializer, FAQSerializer,
    FlattenedCourseRunWithCourseSerializer, ImageSerializer, MinimalCourseRunSerializer, MinimalCourseSerializer,
    MinimalOrganizationSerializer, MinimalProgramCourseSerializer, MinimalProgramSerializer, NestedProgramSerializer,
    OrganizationSerializer, PersonSerializer, PositionSerializer, PrerequisiteSerializer, ProgramSearchSerializer,
    ProgramSerializer, ProgramTypeSerializer, SeatSerializer, SubjectSerializer, TypeaheadCourseRunSearchSerializer,
    TypeaheadProgramSearchSerializer, VideoSerializer
)
from course_discovery.apps.catalogs.tests.factories import CatalogFactory
from course_discovery.apps.core.models import User
from course_discovery.apps.core.tests.factories import UserFactory
from course_discovery.apps.core.tests.helpers import make_image_file
from course_discovery.apps.core.tests.mixins import ElasticsearchTestMixin
from course_discovery.apps.course_metadata.choices import CourseRunStatus, ProgramStatus
from course_discovery.apps.course_metadata.models import Course, CourseRun, Program
from course_discovery.apps.course_metadata.tests.factories import (
    CorporateEndorsementFactory, CourseFactory, CourseRunFactory, EndorsementFactory, ExpectedLearningItemFactory,
    ImageFactory, JobOutlookItemFactory, OrganizationFactory, PersonFactory, PositionFactory, PrerequisiteFactory,
    ProgramFactory, ProgramTypeFactory, SeatFactory, SeatTypeFactory, SubjectFactory, VideoFactory
)
from course_discovery.apps.ietf_language_tags.models import LanguageTag


def json_date_format(datetime_obj):
    return datetime.datetime.strftime(datetime_obj, "%Y-%m-%dT%H:%M:%S.%fZ")


def make_request():
    user = UserFactory()
    request = APIRequestFactory().get('/')
    request.user = user
    return request


def serialize_datetime(d):
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


class MinimalCourseSerializerTests(TestCase):
    serializer_class = MinimalCourseSerializer

    def get_expected_data(self, course, request):
        context = {'request': request}

        return {
            'key': course.key,
            'uuid': str(course.uuid),
            'title': course.title,
            'course_runs': MinimalCourseRunSerializer(course.course_runs, many=True, context=context).data,
            'owners': MinimalOrganizationSerializer(course.authoring_organizations, many=True, context=context).data,
            'image': ImageField().to_representation(course.card_image_url),
        }

    def test_data(self):
        request = make_request()
        organizations = OrganizationFactory()
        course = CourseFactory(authoring_organizations=[organizations])
        CourseRunFactory.create_batch(2, course=course)
        serializer = self.serializer_class(course, context={'request': request})
        expected = self.get_expected_data(course, request)
        self.assertDictEqual(serializer.data, expected)


class CourseSerializerTests(MinimalCourseSerializerTests):
    serializer_class = CourseSerializer

    def get_expected_data(self, course, request):
        expected = super().get_expected_data(course, request)
        expected.update({
            'short_description': course.short_description,
            'full_description': course.full_description,
            'level_type': course.level_type.name,
            'subjects': [],
            'prerequisites': [],
            'expected_learning_items': [],
            'video': VideoSerializer(course.video).data,
            'sponsors': OrganizationSerializer(course.sponsoring_organizations, many=True).data,
            'modified': json_date_format(course.modified),  # pylint: disable=no-member
            'marketing_url': '{url}?{params}'.format(
                url=course.marketing_url,
                params=urlencode({
                    'utm_source': request.user.username,
                    'utm_medium': request.user.referral_tracking_id,
                })
            ),
            'course_runs': CourseRunSerializer(course.course_runs, many=True, context={'request': request}).data,
            'owners': OrganizationSerializer(course.authoring_organizations, many=True).data,
        })

        return expected

    def test_exclude_utm(self):
        request = make_request()
        course = CourseFactory()
        CourseRunFactory.create_batch(3, course=course)
        serializer = self.serializer_class(course, context={'request': request, 'exclude_utm': 1})

        self.assertEqual(serializer.data['marketing_url'], course.marketing_url)


@ddt.ddt
class CourseWithProgramsSerializerTests(CourseSerializerTests):
    serializer_class = CourseWithProgramsSerializer

    def get_expected_data(self, course, request):
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
        self.course = CourseFactory()
        self.deleted_program = ProgramFactory(
            courses=[self.course],
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

    def get_expected_data(self, course_run, request):  # pylint: disable=unused-argument
        return {
            'key': course_run.key,
            'uuid': str(course_run.uuid),
            'title': course_run.title,
            'short_description': course_run.short_description,
            'image': ImageField().to_representation(course_run.card_image_url),
            'marketing_url': '{url}?{params}'.format(
                url=course_run.marketing_url,
                params=urlencode({
                    'utm_source': request.user.username,
                    'utm_medium': request.user.referral_tracking_id,
                })
            ),
            'start': json_date_format(course_run.start),
            'end': json_date_format(course_run.end),
            'enrollment_start': json_date_format(course_run.enrollment_start),
            'enrollment_end': json_date_format(course_run.enrollment_end),
            'pacing_type': course_run.pacing_type,
            'type': course_run.type,
            'seats': SeatSerializer(course_run.seats, many=True).data,
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

    def get_expected_data(self, course_run, request):
        expected = super().get_expected_data(course_run, request)
        expected.update({
            'course': course_run.course.key,
            'key': course_run.key,
            'title': course_run.title,  # pylint: disable=no-member
            'full_description': course_run.full_description,  # pylint: disable=no-member
            'announcement': json_date_format(course_run.announcement),
            'video': VideoSerializer(course_run.video).data,
            'mobile_available': course_run.mobile_available,
            'eligible_for_financial_aid': course_run.eligible_for_financial_aid,
            'hidden': course_run.hidden,
            'content_language': course_run.language.code,
            'transcript_languages': [],
            'min_effort': course_run.min_effort,
            'max_effort': course_run.max_effort,
            'instructors': [],
            'staff': [],
            'seats': [],
            'modified': json_date_format(course_run.modified),  # pylint: disable=no-member
            'level_type': course_run.level_type.name,
            'availability': course_run.availability,
            'reporting_type': course_run.reporting_type,
            'status': course_run.status,
        })

        return expected

    def test_exclude_utm(self):
        request = make_request()
        course_run = CourseRunFactory()
        serializer = self.serializer_class(course_run, context={'request': request, 'exclude_utm': 1})

        self.assertEqual(serializer.data['marketing_url'], course_run.marketing_url)


class CourseRunWithProgramsSerializerTests(TestCase):
    def setUp(self):
        super().setUp()
        self.request = make_request()
        self.course_run = CourseRunFactory()
        self.serializer_context = {'request': self.request}

    def test_data(self):
        serializer = CourseRunWithProgramsSerializer(self.course_run, context=self.serializer_context)
        ProgramFactory(courses=[self.course_run.course])

        expected = CourseRunSerializer(self.course_run, context=self.serializer_context).data
        expected.update({
            'programs': NestedProgramSerializer(
                self.course_run.course.programs,
                many=True,
                context=self.serializer_context
            ).data,
        })

        self.assertDictEqual(serializer.data, expected)

    def test_data_excluded_course_run(self):
        """
        If a course run is excluded on a program, that program should not be
        returned for that course run on the course run endpoint.
        """
        serializer = CourseRunWithProgramsSerializer(self.course_run, context=self.serializer_context)
        ProgramFactory(courses=[self.course_run.course], excluded_course_runs=[self.course_run])
        expected = CourseRunSerializer(self.course_run, context=self.serializer_context).data
        expected.update({
            'programs': [],
        })

        self.assertDictEqual(serializer.data, expected)

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


class FlattenedCourseRunWithCourseSerializerTests(TestCase):  # pragma: no cover
    def serialize_seats(self, course_run):
        seats = {
            'audit': {
                'type': ''
            },
            'honor': {
                'type': ''
            },
            'verified': {
                'type': '',
                'currency': '',
                'price': '',
                'upgrade_deadline': '',
            },
            'professional': {
                'type': '',
                'currency': '',
                'price': '',
                'upgrade_deadline': '',
            },
            'credit': {
                'type': [],
                'currency': [],
                'price': [],
                'upgrade_deadline': [],
                'credit_provider': [],
                'credit_hours': [],
            },
        }

        for seat in course_run.seats.all():
            for key in seats[seat.type].keys():
                if seat.type == 'credit':
                    seats['credit'][key].append(SeatSerializer(seat).data[key])
                else:
                    seats[seat.type][key] = SeatSerializer(seat).data[key]

        for credit_attr in seats['credit']:
            seats['credit'][credit_attr] = ','.join([str(e) for e in seats['credit'][credit_attr]])

        return seats

    def serialize_items(self, organizations, attr):
        return ','.join([getattr(organization, attr) for organization in organizations])

    def get_expected_data(self, request, course_run):
        course = course_run.course
        serializer_context = {'request': request}
        expected = dict(CourseRunSerializer(course_run, context=serializer_context).data)
        expected.update({
            'subjects': self.serialize_items(course.subjects.all(), 'name'),
            'seats': self.serialize_seats(course_run),
            'owners': self.serialize_items(course.authoring_organizations.all(), 'key'),
            'sponsors': self.serialize_items(course.sponsoring_organizations.all(), 'key'),
            'prerequisites': self.serialize_items(course.prerequisites.all(), 'name'),
            'level_type': course_run.level_type.name if course_run.level_type else None,
            'expected_learning_items': self.serialize_items(course.expected_learning_items.all(), 'value'),
            'course_key': course.key,
            'image': ImageField().to_representation(course_run.card_image_url),
        })

        # Remove fields found in CourseRunSerializer, but not in FlattenedCourseRunWithCourseSerializer.
        fields_to_remove = set(CourseRunSerializer.Meta.fields) - set(
            FlattenedCourseRunWithCourseSerializer.Meta.fields)
        for key in fields_to_remove:
            del expected[key]

        return expected

    def test_data(self):
        request = make_request()
        course_run = CourseRunFactory()
        SeatFactory(course_run=course_run)
        serializer_context = {'request': request}
        serializer = FlattenedCourseRunWithCourseSerializer(course_run, context=serializer_context)
        expected = self.get_expected_data(request, course_run)
        self.assertDictEqual(serializer.data, expected)

    def test_data_without_level_type(self):
        """ Verify the serializer handles courses with no level type set. """
        request = make_request()
        course_run = CourseRunFactory(course__level_type=None)
        SeatFactory(course_run=course_run)
        serializer_context = {'request': request}
        serializer = FlattenedCourseRunWithCourseSerializer(course_run, context=serializer_context)
        expected = self.get_expected_data(request, course_run)
        self.assertDictEqual(serializer.data, expected)


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
            CourseRunFactory.create_batch(2, course=course, staff=[person], start=datetime.datetime.now())

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

    def get_expected_data(self, program, request):
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

    def get_expected_data(self, program, request):
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
            'staff': PersonSerializer(program.staff, many=True, context={'request': request}).data,
            'job_outlook_items': [item.value for item in program.job_outlook_items.all()],
            'languages': [serialize_language_to_code(l) for l in program.languages],
            'weeks_to_complete': program.weeks_to_complete,
            'weeks_to_complete_min': program.weeks_to_complete_min,
            'weeks_to_complete_max': program.weeks_to_complete_max,
            'max_hours_effort_per_week': program.max_hours_effort_per_week,
            'min_hours_effort_per_week': program.min_hours_effort_per_week,
            'overview': program.overview,
            'price_ranges': program.price_ranges,
            'subjects': SubjectSerializer(program.subjects, many=True).data,
            'transcript_languages': [serialize_language_to_code(l) for l in program.transcript_languages],
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
            start=datetime.datetime(2014, 2, 1),
        )

        # Create a second run with matching start, but later enrollment_start.
        CourseRunFactory(
            course=course_list[1],
            enrollment_start=datetime.datetime(2014, 1, 2),
            start=datetime.datetime(2014, 2, 1),
        )

        # Create a third run with later start and enrollment_start.
        CourseRunFactory(
            course=course_list[0],
            enrollment_start=datetime.datetime(2014, 2, 1),
            start=datetime.datetime(2014, 3, 1),
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
            start=datetime.datetime(2014, 1, 1),
        )

        # Create a run with later start and empty enrollment_start.
        CourseRunFactory(
            course=course_list[2],
            enrollment_start=None,
            start=datetime.datetime(2014, 2, 1),
        )

        # Create a run with matching start, but later enrollment_start.
        CourseRunFactory(
            course=course_list[1],
            enrollment_start=datetime.datetime(2014, 1, 2),
            start=datetime.datetime(2014, 2, 1),
        )

        # Create a run with later start and enrollment_start.
        CourseRunFactory(
            course=course_list[0],
            enrollment_start=datetime.datetime(2014, 2, 1),
            start=datetime.datetime(2014, 3, 1),
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
            start=datetime.datetime(2014, 2, 1),
        )

        # Create a second run with matching start, but later enrollment_start.
        CourseRunFactory(
            course=course_list[1],
            enrollment_start=datetime.datetime(2014, 1, 2),
            start=datetime.datetime(2014, 2, 1),
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
            end=datetime.datetime.now(pytz.UTC) + datetime.timedelta(days=10),
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

    def get_expected_data(self, program_type, request):
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

    def get_expected_data(self, organization):
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

    def get_expected_data(self, organization):
        expected = super().get_expected_data(organization)
        expected.update({
            'certificate_logo_image_url': organization.certificate_logo_image_url,
            'description': organization.description,
            'homepage_url': organization.homepage_url,
            'logo_image_url': organization.logo_image_url,
            'tags': [self.TAG],
            'marketing_url': organization.marketing_url,
        })

        return expected


class SeatSerializerTests(TestCase):
    def test_data(self):
        course_run = CourseRunFactory()
        seat = SeatFactory(course_run=course_run)
        serializer = SeatSerializer(seat)

        expected = {
            'type': seat.type,
            'price': str(seat.price),
            'currency': seat.currency.code,
            'upgrade_deadline': json_date_format(seat.upgrade_deadline),
            'credit_provider': seat.credit_provider,  # pylint: disable=no-member
            'credit_hours': seat.credit_hours,  # pylint: disable=no-member
            'sku': seat.sku
        }

        self.assertDictEqual(serializer.data, expected)


class PersonSerializerTests(TestCase):
    def test_data(self):
        request = make_request()
        context = {'request': request}
        image_field = StdImageSerializerField()
        image_field._context = context  # pylint: disable=protected-access

        position = PositionFactory()
        person = position.person
        serializer = PersonSerializer(person, context=context)

        expected = {
            'uuid': str(person.uuid),
            'given_name': person.given_name,
            'family_name': person.family_name,
            'bio': person.bio,
            'profile_image_url': person.profile_image_url,
            'profile_image': image_field.to_representation(person.profile_image),
            'position': PositionSerializer(position).data,
            'works': [work.value for work in person.person_works.all()],
            'urls': {
                'facebook': None,
                'twitter': None,
                'blog': None
            },
            'slug': person.slug,
            'email': person.email,
        }

        self.assertDictEqual(serializer.data, expected)


class PositionSerializerTests(TestCase):
    def test_data(self):
        position = PositionFactory()
        serializer = PositionSerializer(position)

        expected = {
            'title': str(position.title),
            'organization_name': position.organization_name,
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
        self.assertTrue(all((course_run.title, course_run.short_description, course_run.marketing_url)))

        expected = {
            'pid': '{}-{}'.format(course_run.key, seat.type),
            'name': course_run.title,
            'desc': course_run.short_description,
            'purl': course_run.marketing_url,
            'price': {
                'actualp': seat.price
            },
            'currency': seat.currency.code,
            'imgurl': course_run.card_image_url,
            'category': 'Other Experiences'
        }
        self.assertDictEqual(serializer.data, expected)


class CourseSearchSerializerTests(TestCase):
    def test_data(self):
        course = CourseFactory()
        serializer = self.serialize_course(course)

        expected = {
            'key': course.key,
            'title': course.title,
            'short_description': course.short_description,
            'full_description': course.full_description,
            'content_type': 'course',
            'aggregation_key': 'course:{}'.format(course.key),
        }
        assert serializer.data == expected

    def serialize_course(self, course):
        """ Serializes the given `Course` as a search result. """
        result = SearchQuerySet().models(Course).filter(key=course.key)[0]
        serializer = CourseSearchSerializer(result)
        return serializer


class CourseRunSearchSerializerTests(ElasticsearchTestMixin, TestCase):
    def test_data(self):
        course_run = CourseRunFactory(transcript_languages=LanguageTag.objects.filter(code__in=['en-us', 'zh-cn']),
                                      authoring_organizations=[OrganizationFactory()])
        program = ProgramFactory(courses=[course_run.course])
        self.reindex_courses(program)
        serializer = self.serialize_course_run(course_run)
        course_run_key = CourseKey.from_string(course_run.key)
        orgs = course_run.authoring_organizations.all()
        expected = {
            'transcript_languages': [serialize_language(l) for l in course_run.transcript_languages.all()],
            'min_effort': course_run.min_effort,
            'max_effort': course_run.max_effort,
            'weeks_to_complete': course_run.weeks_to_complete,
            'short_description': course_run.short_description,
            'start': serialize_datetime(course_run.start),
            'end': serialize_datetime(course_run.end),
            'enrollment_start': serialize_datetime(course_run.enrollment_start),
            'enrollment_end': serialize_datetime(course_run.enrollment_end),
            'key': course_run.key,
            'marketing_url': course_run.marketing_url,
            'pacing_type': course_run.pacing_type,
            'mobile_available': course_run.mobile_available,
            'language': serialize_language(course_run.language),
            'full_description': course_run.full_description,
            'title': course_run.title,
            'content_type': 'courserun',
            'org': course_run_key.org,
            'number': course_run_key.course,
            'seat_types': course_run.seat_types,
            'image_url': course_run.card_image_url,
            'type': course_run.type,
            'level_type': course_run.level_type.name,
            'availability': course_run.availability,
            'published': course_run.status == CourseRunStatus.Published,
            'partner': course_run.course.partner.short_code,
            'program_types': course_run.program_types,
            'logo_image_urls': [org.logo_image_url for org in orgs],
            'authoring_organization_uuids': get_uuids(course_run.authoring_organizations.all()),
            'subject_uuids': get_uuids(course_run.subjects.all()),
            'staff_uuids': get_uuids(course_run.staff.all()),
            'aggregation_key': 'courserun:{}'.format(course_run.course.key),
        }
        assert serializer.data == expected

    def serialize_course_run(self, course_run):
        """ Serializes the given `CourseRun` as a search result. """
        result = SearchQuerySet().models(CourseRun).filter(key=course_run.key)[0]
        serializer = CourseRunSearchSerializer(result)
        return serializer

    def test_data_without_serializers(self):
        """ Verify a null `LevelType` is properly serialized as None. """
        course_run = CourseRunFactory(course__level_type=None)
        serializer = self.serialize_course_run(course_run)
        assert serializer.data['level_type'] is None


class ProgramSearchSerializerTests(TestCase):
    def _create_expected_data(self, program):
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
            'subject_uuids': get_uuids(
                itertools.chain.from_iterable(course.subjects.all() for course in program.courses.all())
            ),
            'staff_uuids': get_uuids(
                itertools.chain.from_iterable(course.staff.all() for course in list(program.course_runs))
            ),
            'aggregation_key': 'program:{}'.format(program.uuid),
            'weeks_to_complete_min': program.weeks_to_complete_min,
            'weeks_to_complete_max': program.weeks_to_complete_max,
            'min_hours_effort_per_week': program.min_hours_effort_per_week,
            'max_hours_effort_per_week': program.max_hours_effort_per_week,
            'language': [serialize_language(language) for language in program.languages],
            'hidden': program.hidden,
        }

    def test_data(self):
        authoring_organization, crediting_organization = OrganizationFactory.create_batch(2)
        program = ProgramFactory(authoring_organizations=[authoring_organization],
                                 credit_backing_organizations=[crediting_organization])

        # NOTE: This serializer expects SearchQuerySet results, so we run a search on the newly-created object
        # to generate such a result.
        result = SearchQuerySet().models(Program).filter(uuid=program.uuid)[0]
        serializer = ProgramSearchSerializer(result)

        expected = self._create_expected_data(program)
        assert serializer.data == expected

    def test_data_without_organizations(self):
        """ Verify the serializer serialized programs with no associated organizations.
        In such cases the organizations value should be an empty array. """
        program = ProgramFactory(authoring_organizations=[], credit_backing_organizations=[])

        result = SearchQuerySet().models(Program).filter(uuid=program.uuid)[0]
        serializer = ProgramSearchSerializer(result)

        expected = self._create_expected_data(program)
        assert serializer.data == expected

    def test_data_with_languages(self):
        """
        Verify that program languages are serialized.
        """
        course_run = CourseRunFactory(
            language=LanguageTag.objects.get(code='en-us'),
            authoring_organizations=[OrganizationFactory()]
        )

        CourseRunFactory(
            course=course_run.course,
            language=LanguageTag.objects.get(code='zh-cmn')
        )

        program = ProgramFactory(courses=[course_run.course])

        result = SearchQuerySet().models(Program).filter(uuid=program.uuid)[0]
        serializer = ProgramSearchSerializer(result)

        expected = self._create_expected_data(program)
        assert serializer.data == expected
        assert {'English', 'Chinese - Mandarin'} == {*expected['language']}


class TypeaheadCourseRunSearchSerializerTests(TestCase):
    def test_data(self):
        authoring_organization = OrganizationFactory()
        course_run = CourseRunFactory(authoring_organizations=[authoring_organization])
        serialized_course = self.serialize_course_run(course_run)

        expected = {
            'key': course_run.key,
            'title': course_run.title,
            'orgs': [org.key for org in course_run.authoring_organizations.all()],
            'marketing_url': course_run.marketing_url,
        }
        assert serialized_course.data == expected

    def serialize_course_run(self, course_run):
        """ Serializes the given `CourseRun` as a typeahead result. """
        result = SearchQuerySet().models(CourseRun).filter(key=course_run.key)[0]
        serializer = TypeaheadCourseRunSearchSerializer(result)
        return serializer


class TypeaheadProgramSearchSerializerTests(TestCase):
    def _create_expected_data(self, program):
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
        expected = self._create_expected_data(program)
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
        serializer = TypeaheadProgramSearchSerializer(result)
        return serializer
