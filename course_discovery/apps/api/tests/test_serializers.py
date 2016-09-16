import unittest
from datetime import datetime
from urllib.parse import urlencode

import ddt
from django.test import TestCase
from haystack.query import SearchQuerySet
from opaque_keys.edx.keys import CourseKey
from rest_framework.test import APIRequestFactory

from course_discovery.apps.api.fields import ImageField
from course_discovery.apps.api.serializers import (
    CatalogSerializer, CourseSerializer, CourseRunSerializer, ContainedCoursesSerializer, ImageSerializer,
    SubjectSerializer, PrerequisiteSerializer, VideoSerializer, OrganizationSerializer, SeatSerializer,
    PersonSerializer, AffiliateWindowSerializer, ContainedCourseRunsSerializer, CourseRunSearchSerializer,
    ProgramSerializer, ProgramSearchSerializer, ProgramCourseSerializer, NestedProgramSerializer,
    CourseRunWithProgramsSerializer, CourseWithProgramsSerializer, CorporateEndorsementSerializer,
    FAQSerializer, EndorsementSerializer, PositionSerializer, FlattenedCourseRunWithCourseSerializer
)
from course_discovery.apps.catalogs.tests.factories import CatalogFactory
from course_discovery.apps.core.models import User
from course_discovery.apps.core.tests.factories import UserFactory
from course_discovery.apps.core.tests.helpers import make_image_file
from course_discovery.apps.course_metadata.choices import CourseRunStatus, ProgramStatus
from course_discovery.apps.course_metadata.models import CourseRun, Program
from course_discovery.apps.course_metadata.tests.factories import (
    CourseFactory, CourseRunFactory, SubjectFactory, PrerequisiteFactory, ImageFactory, VideoFactory,
    OrganizationFactory, PersonFactory, SeatFactory, ProgramFactory, CorporateEndorsementFactory, EndorsementFactory,
    JobOutlookItemFactory, ExpectedLearningItemFactory, PositionFactory
)
from course_discovery.apps.ietf_language_tags.models import LanguageTag


# pylint:disable=no-member

def json_date_format(datetime_obj):
    return datetime.strftime(datetime_obj, "%Y-%m-%dT%H:%M:%S.%fZ")


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


class CatalogSerializerTests(TestCase):
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


class CourseSerializerTests(TestCase):
    def test_data(self):
        course = CourseFactory()
        video = course.video

        request = make_request()

        CourseRunFactory.create_batch(3, course=course)
        serializer = CourseWithProgramsSerializer(course, context={'request': request})

        expected = {
            'key': course.key,
            'title': course.title,
            'short_description': course.short_description,
            'full_description': course.full_description,
            'level_type': course.level_type.name,
            'subjects': [],
            'prerequisites': [],
            'expected_learning_items': [],
            'image': ImageField().to_representation(course.card_image_url),
            'video': VideoSerializer(video).data,
            'owners': OrganizationSerializer(course.authoring_organizations, many=True).data,
            'sponsors': OrganizationSerializer(course.sponsoring_organizations, many=True).data,
            'modified': json_date_format(course.modified),  # pylint: disable=no-member
            'course_runs': CourseRunSerializer(course.course_runs, many=True, context={'request': request}).data,
            'marketing_url': '{url}?{params}'.format(
                url=course.marketing_url,
                params=urlencode({
                    'utm_source': request.user.username,
                    'utm_medium': request.user.referral_tracking_id,
                })
            ),
            'programs': NestedProgramSerializer(course.programs, many=True, context={'request': request}).data,
        }

        self.assertDictEqual(serializer.data, expected)


class CourseRunSerializerTests(TestCase):
    def test_data(self):
        request = make_request()
        course_run = CourseRunFactory()
        course = course_run.course
        video = course_run.video
        serializer = CourseRunSerializer(course_run, context={'request': request})
        ProgramFactory(courses=[course])

        expected = {
            'course': course_run.course.key,
            'key': course_run.key,
            'title': course_run.title,  # pylint: disable=no-member
            'short_description': course_run.short_description,  # pylint: disable=no-member
            'full_description': course_run.full_description,  # pylint: disable=no-member
            'start': json_date_format(course_run.start),
            'end': json_date_format(course_run.end),
            'enrollment_start': json_date_format(course_run.enrollment_start),
            'enrollment_end': json_date_format(course_run.enrollment_end),
            'announcement': json_date_format(course_run.announcement),
            'image': ImageField().to_representation(course_run.card_image_url),
            'video': VideoSerializer(video).data,
            'pacing_type': course_run.pacing_type,
            'content_language': course_run.language.code,
            'transcript_languages': [],
            'min_effort': course_run.min_effort,
            'max_effort': course_run.max_effort,
            'instructors': [],
            'staff': [],
            'seats': [],
            'modified': json_date_format(course_run.modified),  # pylint: disable=no-member
            'marketing_url': '{url}?{params}'.format(
                url=course_run.marketing_url,
                params=urlencode({
                    'utm_source': request.user.username,
                    'utm_medium': request.user.referral_tracking_id,
                })
            ),
            'level_type': course_run.level_type.name,
            'availability': course_run.availability,
        }

        self.assertDictEqual(serializer.data, expected)


class CourseRunWithProgramsSerializerTests(TestCase):
    def test_data(self):
        request = make_request()
        course_run = CourseRunFactory()
        serializer_context = {'request': request}
        serializer = CourseRunWithProgramsSerializer(course_run, context=serializer_context)
        ProgramFactory(courses=[course_run.course])

        expected = CourseRunSerializer(course_run, context=serializer_context).data
        expected.update({
            'programs': NestedProgramSerializer(course_run.course.programs, many=True, context=serializer_context).data,
        })

        self.assertDictEqual(serializer.data, expected)


@unittest.skip('This test is disabled until we can determine why assertDictEqual() fails for two equivalent inputs.')
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

        for credit_attr in seats['credit'].keys():
            seats['credit'][credit_attr] = ','.join([str(e) for e in seats['credit'][credit_attr]])

        return seats

    def serialize_items(self, organizations, attr):
        return ','.join([getattr(organization, attr) for organization in organizations])

    def get_expected_data(self, request, course_run):
        course = course_run.course
        serializer_context = {'request': request}
        expected = CourseRunSerializer(course_run, context=serializer_context).data
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


@ddt.ddt
class ProgramCourseSerializerTests(TestCase):
    def setUp(self):
        super(ProgramCourseSerializerTests, self).setUp()
        self.request = make_request()
        self.course_list = CourseFactory.create_batch(3)
        self.program = ProgramFactory(courses=self.course_list)

    def test_no_run(self):
        """
        Make sure that if a course has no runs, the serializer still works as expected
        """
        serializer = ProgramCourseSerializer(
            self.course_list,
            many=True,
            context={'request': self.request, 'program': self.program, 'course_runs': self.program.course_runs}
        )

        expected = CourseSerializer(self.course_list, many=True, context={'request': self.request}).data

        self.assertSequenceEqual(serializer.data, expected)

    def test_with_runs(self):
        for course in self.course_list:
            CourseRunFactory.create_batch(2, course=course)
        serializer = ProgramCourseSerializer(
            self.course_list,
            many=True,
            context={'request': self.request, 'program': self.program, 'course_runs': self.program.course_runs}
        )

        expected = CourseSerializer(self.course_list, many=True, context={'request': self.request}).data

        self.assertSequenceEqual(serializer.data, expected)

    def test_with_exclusions(self):
        """
        Test serializer with course_run exclusions within program
        """
        course = CourseFactory()
        excluded_runs = []
        course_runs = CourseRunFactory.create_batch(2, course=course)
        excluded_runs.append(course_runs[0])
        program = ProgramFactory(courses=[course], excluded_course_runs=excluded_runs)

        serializer_context = {'request': self.request, 'program': program, 'course_runs': program.course_runs}
        serializer = ProgramCourseSerializer(course, context=serializer_context)

        expected = CourseSerializer(course, context=serializer_context).data
        expected['course_runs'] = CourseRunSerializer([course_runs[1]], many=True,
                                                      context={'request': self.request}).data
        self.assertDictEqual(serializer.data, expected)

    @ddt.data(
        [CourseRunStatus.Unpublished, 1],
        [CourseRunStatus.Unpublished, 0],
        [CourseRunStatus.Published, 1],
        [CourseRunStatus.Published, 0]
    )
    @ddt.unpack
    def test_with_published_only_querystring(self, course_run_status, published_course_runs_only):
        """
        Test the serializer's ability to filter out course_runs based on
        "published_course_runs_only" query string
        """
        expected = CourseSerializer(self.course_list, many=True, context={'request': self.request}).data

        for course in self.course_list:
            CourseRunFactory.create_batch(2, status=course_run_status, course=course)
        serializer = ProgramCourseSerializer(
            self.course_list,
            many=True,
            context={
                'request': self.request,
                'program': self.program,
                'published_course_runs_only': published_course_runs_only,
                'course_runs': self.program.course_runs
            }
        )
        validate_data = serializer.data

        if not published_course_runs_only or course_run_status != CourseRunStatus.Unpublished:
            expected = CourseSerializer(self.course_list, many=True, context={'request': self.request}).data

        self.assertSequenceEqual(validate_data, expected)


class ProgramSerializerTests(TestCase):
    def test_data(self):
        request = make_request()
        org_list = OrganizationFactory.create_batch(1)
        course_list = CourseFactory.create_batch(3)
        for course in course_list:
            CourseRunFactory.create_batch(
                3,
                course=course,
                enrollment_start=datetime(2014, 1, 1),
                start=datetime(2014, 1, 1)
            )
        corporate_endorsements = CorporateEndorsementFactory.create_batch(1)
        individual_endorsements = EndorsementFactory.create_batch(1)
        staff = PersonFactory.create_batch(1)
        job_outlook_items = JobOutlookItemFactory.create_batch(1)
        expected_learning_items = ExpectedLearningItemFactory.create_batch(1)
        program = ProgramFactory(
            authoring_organizations=org_list,
            courses=course_list,
            credit_backing_organizations=org_list,
            corporate_endorsements=corporate_endorsements,
            individual_endorsements=individual_endorsements,
            expected_learning_items=expected_learning_items,
            staff=staff,
            job_outlook_items=job_outlook_items,
        )
        program.banner_image = make_image_file('test_banner.jpg')
        program.save()
        serializer = ProgramSerializer(program, context={'request': request})
        expected_banner_image_urls = {
            size_key: {
                'url': '{}{}'.format(
                    'http://testserver',
                    getattr(program.banner_image, size_key).url
                ),
                'width': program.banner_image.field.variations[size_key]['width'],
                'height': program.banner_image.field.variations[size_key]['height']
            }
            for size_key in program.banner_image.field.variations
        }

        expected = {
            'uuid': str(program.uuid),
            'title': program.title,
            'subtitle': program.subtitle,
            'type': program.type.name,
            'marketing_slug': program.marketing_slug,
            'marketing_url': program.marketing_url,
            'card_image_url': program.card_image_url,
            'banner_image_url': program.banner_image_url,
            'video': None,
            'banner_image': expected_banner_image_urls,
            'authoring_organizations': OrganizationSerializer(program.authoring_organizations, many=True).data,
            'credit_redemption_overview': program.credit_redemption_overview,
            'courses': ProgramCourseSerializer(
                program.courses,
                many=True,
                context={'request': request, 'program': program, 'course_runs': program.course_runs}
            ).data,
            'corporate_endorsements': CorporateEndorsementSerializer(program.corporate_endorsements, many=True).data,
            'credit_backing_organizations': OrganizationSerializer(
                program.credit_backing_organizations,
                many=True
            ).data,
            'expected_learning_items': [item.value for item in program.expected_learning_items.all()],
            'faq': FAQSerializer(program.faq, many=True).data,
            'individual_endorsements': EndorsementSerializer(program.individual_endorsements, many=True).data,
            'staff': PersonSerializer(program.staff, many=True).data,
            'job_outlook_items': [item.value for item in program.job_outlook_items.all()],
            'languages': [serialize_language_to_code(l) for l in program.languages],
            'weeks_to_complete': program.weeks_to_complete,
            'max_hours_effort_per_week': None,
            'min_hours_effort_per_week': None,
            'overview': None,
            'price_ranges': [],
            'status': program.status,
            'subjects': [],
            'transcript_languages': [],
        }

        self.assertDictEqual(serializer.data, expected)

    def test_with_exclusions(self):
        """
        Verify we can specify program excluded_course_runs and the serializers will
        render the course_runs with exclusions
        """
        request = make_request()
        org_list = OrganizationFactory.create_batch(1)
        course_list = CourseFactory.create_batch(4)
        excluded_runs = []
        for course in course_list:
            course_runs = CourseRunFactory.create_batch(
                3,
                course=course,
                enrollment_start=datetime(2014, 1, 1),
                start=datetime(2014, 1, 1)
            )
            excluded_runs.append(course_runs[0])

        program = ProgramFactory(
            authoring_organizations=org_list,
            courses=course_list,
            excluded_course_runs=excluded_runs
        )
        serializer = ProgramSerializer(program, context={'request': request})

        expected = {
            'uuid': str(program.uuid),
            'title': program.title,
            'subtitle': program.subtitle,
            'type': program.type.name,
            'marketing_slug': program.marketing_slug,
            'marketing_url': program.marketing_url,
            'card_image_url': program.card_image_url,
            'banner_image': {},
            'banner_image_url': program.banner_image_url,
            'video': None,
            'authoring_organizations': OrganizationSerializer(program.authoring_organizations, many=True).data,
            'credit_redemption_overview': program.credit_redemption_overview,
            'courses': ProgramCourseSerializer(
                program.courses,
                many=True,
                context={'request': request, 'program': program, 'course_runs': program.course_runs}
            ).data,
            'corporate_endorsements': CorporateEndorsementSerializer(program.corporate_endorsements, many=True).data,
            'credit_backing_organizations': OrganizationSerializer(
                program.credit_backing_organizations,
                many=True
            ).data,
            'expected_learning_items': [],
            'faq': FAQSerializer(program.faq, many=True).data,
            'individual_endorsements': EndorsementSerializer(program.individual_endorsements, many=True).data,
            'staff': PersonSerializer(program.staff, many=True).data,
            'job_outlook_items': [],
            'languages': [serialize_language_to_code(l) for l in program.languages],
            'weeks_to_complete': program.weeks_to_complete,
            'max_hours_effort_per_week': None,
            'min_hours_effort_per_week': None,
            'overview': None,
            'price_ranges': [],
            'status': program.status,
            'subjects': [],
            'transcript_languages': [],
        }

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
            start=datetime(2014, 2, 1),
        )

        # Create a second run with matching start, but later enrollment_start.
        CourseRunFactory(
            course=course_list[1],
            enrollment_start=datetime(2014, 1, 2),
            start=datetime(2014, 2, 1),
        )

        # Create a third run with later start and enrollment_start.
        CourseRunFactory(
            course=course_list[0],
            enrollment_start=datetime(2014, 2, 1),
            start=datetime(2014, 3, 1),
        )

        program = ProgramFactory(courses=course_list)
        serializer = ProgramSerializer(program, context={'request': request})

        expected = ProgramCourseSerializer(
            # The expected ordering is the reverse of course_list.
            course_list[::-1],
            many=True,
            context={'request': request, 'program': program, 'course_runs': program.course_runs}
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
            start=datetime(2014, 1, 1),
        )

        # Create a run with later start and empty enrollment_start.
        CourseRunFactory(
            course=course_list[2],
            enrollment_start=None,
            start=datetime(2014, 2, 1),
        )

        # Create a run with matching start, but later enrollment_start.
        CourseRunFactory(
            course=course_list[1],
            enrollment_start=datetime(2014, 1, 2),
            start=datetime(2014, 2, 1),
        )

        # Create a run with later start and enrollment_start.
        CourseRunFactory(
            course=course_list[0],
            enrollment_start=datetime(2014, 2, 1),
            start=datetime(2014, 3, 1),
        )

        program = ProgramFactory(courses=course_list, excluded_course_runs=[excluded_run])
        serializer = ProgramSerializer(program, context={'request': request})

        expected = ProgramCourseSerializer(
            # The expected ordering is the reverse of course_list.
            course_list[::-1],
            many=True,
            context={'request': request, 'program': program, 'course_runs': program.course_runs}
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
            start=datetime(2014, 2, 1),
        )

        # Create a second run with matching start, but later enrollment_start.
        CourseRunFactory(
            course=course_list[1],
            enrollment_start=datetime(2014, 1, 2),
            start=datetime(2014, 2, 1),
        )

        # Create a third run with empty start and enrollment_start.
        CourseRunFactory(
            course=course_list[0],
            enrollment_start=None,
            start=None,
        )

        program = ProgramFactory(courses=course_list)
        serializer = ProgramSerializer(program, context={'request': request})

        expected = ProgramCourseSerializer(
            # The expected ordering is the reverse of course_list.
            course_list[::-1],
            many=True,
            context={'request': request, 'program': program, 'course_runs': program.course_runs}
        ).data

        self.assertEqual(serializer.data['courses'], expected)


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


class OrganizationSerializerTests(TestCase):
    def test_data(self):
        organization = OrganizationFactory()
        TAG = 'test'
        organization.tags.add(TAG)
        serializer = OrganizationSerializer(organization)

        expected = {
            'key': organization.key,
            'name': organization.name,
            'description': organization.description,
            'homepage_url': organization.homepage_url,
            'logo_image_url': organization.logo_image_url,
            'tags': [TAG],
            'marketing_url': organization.marketing_url,
        }

        self.assertDictEqual(serializer.data, expected)


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
            'credit_hours': seat.credit_hours  # pylint: disable=no-member
        }

        self.assertDictEqual(serializer.data, expected)


class PersonSerializerTests(TestCase):
    def test_data(self):
        position = PositionFactory()
        person = position.person
        serializer = PersonSerializer(person)

        expected = {
            'uuid': str(person.uuid),
            'given_name': person.given_name,
            'family_name': person.family_name,
            'bio': person.bio,
            'profile_image_url': person.profile_image_url,
            'position': PositionSerializer(position).data,
            'slug': person.slug,
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


class CourseRunSearchSerializerTests(TestCase):
    def test_data(self):
        course_run = CourseRunFactory(transcript_languages=LanguageTag.objects.filter(code__in=['en-us', 'zh-cn']))
        ProgramFactory(courses=[course_run.course])
        serializer = self.serialize_course_run(course_run)
        course_run_key = CourseKey.from_string(course_run.key)

        expected = {
            'transcript_languages': [serialize_language(l) for l in course_run.transcript_languages.all()],
            'short_description': course_run.short_description,
            'start': serialize_datetime(course_run.start),
            'end': serialize_datetime(course_run.end),
            'enrollment_start': serialize_datetime(course_run.enrollment_start),
            'enrollment_end': serialize_datetime(course_run.enrollment_end),
            'key': course_run.key,
            'marketing_url': course_run.marketing_url,
            'pacing_type': course_run.pacing_type,
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
            'authoring_organization_uuids': get_uuids(course_run.authoring_organizations.all()),
            'subject_uuids': get_uuids(course_run.subjects.all()),
            'staff_uuids': get_uuids(course_run.staff.all())
        }
        self.assertDictEqual(serializer.data, expected)

    def serialize_course_run(self, course_run):
        """ Serializes the given `CourseRun` as a search result. """
        result = SearchQuerySet().models(CourseRun).filter(key=course_run.key)[0]
        serializer = CourseRunSearchSerializer(result)
        return serializer

    def test_data_without_serializers(self):
        """ Verify a null `LevelType` is properly serialized as None. """
        course_run = CourseRunFactory(course__level_type=None)
        serializer = self.serialize_course_run(course_run)
        self.assertEqual(serializer.data['level_type'], None)


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
            'subject_uuids': get_uuids([course.subjects for course in program.courses.all()]),
            'staff_uuids': get_uuids([course.staff for course in program.course_runs.all()])
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
        self.assertDictEqual(serializer.data, expected)

    def test_data_without_organizations(self):
        """ Verify the serializer serialized programs with no associated organizations.
        In such cases the organizations value should be an empty array. """
        program = ProgramFactory(authoring_organizations=[], credit_backing_organizations=[])

        result = SearchQuerySet().models(Program).filter(uuid=program.uuid)[0]
        serializer = ProgramSearchSerializer(result)

        expected = self._create_expected_data(program)
        self.assertDictEqual(serializer.data, expected)
