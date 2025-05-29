# pylint: disable=no-member,test-inherits-tests
import datetime

import ddt
import mock
import pytest
from django.test import TestCase
from pytz import UTC
from rest_framework.test import APIRequestFactory
from waffle.models import Switch
from waffle.testutils import override_switch

from course_discovery.apps.api.fields import StdImageSerializerField
from course_discovery.apps.api.serializers import (
    ContainedCourseRunsSerializer, ContainedCoursesSerializer,
    ContentTypeSerializer,
    CourseRunSerializer,
    CourseSerializer,
    MinimalCourseRunSerializer, MinimalCourseSerializer,
    MinimalOrganizationSerializer, MinimalProgramCourseSerializer, MinimalProgramSerializer,
    OrganizationSerializer, PersonSerializer, PositionSerializer,
    ProgramSerializer, ProgramTypeSerializer, SubjectSerializer,
    TypeaheadProgramSearchSerializer,
    get_utm_source_for_user
)
from course_discovery.apps.api.tests.mixins import SiteMixin
from course_discovery.apps.core.models import Partner
from course_discovery.apps.core.tests.factories import PartnerFactory, UserFactory
from course_discovery.apps.core.tests.mixins import LMSAPIClientMixin
from course_discovery.apps.course_metadata.choices import CourseRunStatus
from course_discovery.apps.course_metadata.models import Program
from course_discovery.apps.course_metadata.tests.factories import (
    CourseFactory, CourseRunFactory,
    OrganizationFactory, PositionFactory,
    ProgramFactory, ProgramTypeFactory, SeatFactory, SeatTypeFactory, SubjectFactory
)


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
        course = CourseFactory(partner=self.partner)
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
            'modified': json_date_format(course_run.modified),  # pylint: disable=no-member
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
        serializer = CourseRunSerializer(self.course_run, context=self.serializer_context)
        ProgramFactory(courses=[self.course_run.course])
        self.assertDictEqual(serializer.data, self.get_expected_data(self.course_run, self.request))

    def test_data_excluded_course_run(self):
        """
        If a course run is excluded on a program, that program should not be
        returned for that course run on the course run endpoint.
        """
        serializer = CourseRunSerializer(self.course_run, context=self.serializer_context)
        ProgramFactory(courses=[self.course_run.course])
        expected = CourseRunSerializer(self.course_run, context=self.serializer_context).data
        assert serializer.data == expected

    @classmethod
    def get_expected_data(cls, course_run, request):
        return CourseRunSerializer(course_run, context={'request': request}).data


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

        courses = CourseFactory.create_batch(3)
        for course in courses:
            CourseRunFactory.create_batch(2, course=course, start=datetime.datetime.now(UTC))

        return ProgramFactory(
            courses=courses,
        )

    @classmethod
    def get_expected_data(cls, program, request):
        image_field = StdImageSerializerField()
        image_field._context = {'request': request}  # pylint: disable=protected-access

        return {
            'uuid': str(program.uuid),
            'title': program.title,
            'type': program.type.name,
            'status': program.status,
            'courses': MinimalProgramCourseSerializer(
                program.courses,
                many=True,
                context={
                    'request': request,
                    'program': program,
                    'course_runs': list(program.course_runs),
                }).data,
            'card_image_url': program.card_image_url,
            'languages': program.languages,
            'visibility': program.visibility,
            'partner': program.partner,
            'duration': program.duration,
            'language': program.language,
            'start': program.start,
            'end': program.end,
            'enrollment_start': program.enrollment_start,
            'enrollment_end': program.enrollment_end,
        }

    # def test_data(self):
    #     request = make_request()
    #     program = self.create_program()
    #     serializer = self.serializer_class(program, context={'request': request})
    #     expected = self.get_expected_data(program, request)
    #     self.assertDictEqual(serializer.data, expected)


class ProgramSerializerTests(MinimalProgramSerializerTests):
    serializer_class = ProgramSerializer

    @classmethod
    def get_expected_data(cls, program, request):
        expected = super().get_expected_data(program, request)
        expected.update({
            'languages': [serialize_language_to_code(l) for l in program.languages] if program.languages else [],
        })
        return expected

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
