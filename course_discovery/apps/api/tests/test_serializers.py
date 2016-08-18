from datetime import datetime
from urllib.parse import urlencode

import ddt
from django.test import TestCase
from haystack.query import SearchQuerySet
from opaque_keys.edx.keys import CourseKey
from rest_framework.test import APIRequestFactory

from course_discovery.apps.api.serializers import (
    CatalogSerializer, CourseSerializer, CourseRunSerializer, ContainedCoursesSerializer, ImageSerializer,
    SubjectSerializer, PrerequisiteSerializer, VideoSerializer, OrganizationSerializer, SeatSerializer,
    PersonSerializer, AffiliateWindowSerializer, ContainedCourseRunsSerializer, CourseRunSearchSerializer,
    ProgramSerializer, ProgramSearchSerializer, ProgramCourseSerializer
)
from course_discovery.apps.catalogs.tests.factories import CatalogFactory
from course_discovery.apps.core.models import User
from course_discovery.apps.core.tests.factories import UserFactory
from course_discovery.apps.core.tests.helpers import make_image_file
from course_discovery.apps.course_metadata.models import CourseRun, Program
from course_discovery.apps.course_metadata.tests.factories import (
    CourseFactory, CourseRunFactory, SubjectFactory, PrerequisiteFactory, ImageFactory, VideoFactory,
    OrganizationFactory, PersonFactory, SeatFactory, ProgramFactory
)


# pylint:disable=no-member

def json_date_format(datetime_obj):
    return datetime.strftime(datetime_obj, "%Y-%m-%dT%H:%M:%S.%fZ")


def make_request():
    user = UserFactory()
    request = APIRequestFactory().get('/')
    request.user = user
    return request


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
        image = course.image
        video = course.video

        request = make_request()

        CourseRunFactory.create_batch(3, course=course)
        serializer = CourseSerializer(course, context={'request': request})

        expected = {
            'key': course.key,
            'title': course.title,
            'short_description': course.short_description,
            'full_description': course.full_description,
            'level_type': course.level_type.name,
            'subjects': [],
            'prerequisites': [],
            'expected_learning_items': [],
            'image': ImageSerializer(image).data,
            'video': VideoSerializer(video).data,
            'owners': [],
            'sponsors': [],
            'modified': json_date_format(course.modified),  # pylint: disable=no-member
            'course_runs': CourseRunSerializer(course.course_runs, many=True, context={'request': request}).data,
            'marketing_url': '{url}?{params}'.format(
                url=course.marketing_url,
                params=urlencode({
                    'utm_source': request.user.username,
                    'utm_medium': request.user.referral_tracking_id,
                })
            )
        }

        self.assertDictEqual(serializer.data, expected)

    def test_data_url_none(self):
        """
        Verify that the course serializer does not attempt to add URL
        parameters if the course has no marketing URL.
        """
        course = CourseFactory(marketing_url=None)
        request = make_request()
        serializer = CourseSerializer(course, context={'request': request})
        self.assertEqual(serializer.data['marketing_url'], None)


class CourseRunSerializerTests(TestCase):
    def test_data(self):
        request = make_request()
        course_run = CourseRunFactory()
        image = course_run.image
        video = course_run.video
        serializer = CourseRunSerializer(course_run, context={'request': request})

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
            'image': ImageSerializer(image).data,
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

    def test_data_url_none(self):
        """
        Verify that the course run serializer does not attempt to add URL
        parameters if the course has no marketing URL.
        """
        course_run = CourseRunFactory(marketing_url=None)
        request = make_request()
        serializer = CourseRunSerializer(course_run, context={'request': request})
        self.assertEqual(serializer.data['marketing_url'], None)


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
            context={'request': self.request, 'program': self.program}
        )

        expected = CourseSerializer(self.course_list, many=True, context={'request': self.request}).data

        self.assertSequenceEqual(serializer.data, expected)

    def test_with_runs(self):
        for course in self.course_list:
            CourseRunFactory.create_batch(2, course=course)
        serializer = ProgramCourseSerializer(
            self.course_list,
            many=True,
            context={'request': self.request, 'program': self.program}
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

        serializer = ProgramCourseSerializer(
            course,
            context={'request': self.request, 'program': program}
        )

        expected = {
            'key': course.key,
            'title': course.title,
            'short_description': course.short_description,
            'full_description': course.full_description,
            'level_type': course.level_type.name,
            'subjects': [],
            'prerequisites': [],
            'expected_learning_items': [],
            'image': ImageSerializer(course.image).data,
            'video': VideoSerializer(course.video).data,
            'owners': [],
            'sponsors': [],
            'modified': json_date_format(course.modified),  # pylint: disable=no-member
            'course_runs': CourseRunSerializer([course_runs[1]], many=True, context={'request': self.request}).data,
            'marketing_url': '{url}?{params}'.format(
                url=course.marketing_url,
                params=urlencode({
                    'utm_source': self.request.user.username,
                    'utm_medium': self.request.user.referral_tracking_id,
                })
            )
        }

        self.assertDictEqual(serializer.data, expected)


class ProgramSerializerTests(TestCase):
    def test_data(self):
        request = make_request()
        org_list = OrganizationFactory.create_batch(1)
        course_list = CourseFactory.create_batch(3)
        program = ProgramFactory(authoring_organizations=org_list, courses=course_list)
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
            'banner_image': expected_banner_image_urls,
            'authoring_organizations': OrganizationSerializer(program.authoring_organizations, many=True).data,
            'courses': ProgramCourseSerializer(
                program.courses,
                many=True,
                context={'request': request, 'program': program}
            ).data,
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
            course_runs = CourseRunFactory.create_batch(3, course=course)
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
            'authoring_organizations': OrganizationSerializer(program.authoring_organizations, many=True).data,
            'courses': ProgramCourseSerializer(
                program.courses,
                many=True,
                context={'request': request, 'program': program}
            ).data,
        }

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
        (SubjectFactory, SubjectSerializer),
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
            'tags': [TAG],
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
        person = PersonFactory()
        serializer = PersonSerializer(person)

        expected = {
            'uuid': str(person.uuid),
            'given_name': person.given_name,
            'family_name': person.family_name,
            'bio': person.bio,
            'profile_image_url': person.profile_image_url,
            'slug': person.slug,
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
            'imgurl': course_run.image.src,
            'category': 'Other Experiences'
        }
        self.assertDictEqual(serializer.data, expected)


class CourseRunSearchSerializerTests(TestCase):
    def serialize_datetime(self, d):
        return d.strftime('%Y-%m-%dT%H:%M:%S') if d else None

    def serialize_language(self, language):
        return language.macrolanguage

    def test_data(self):
        course_run = CourseRunFactory()
        course_run_key = CourseKey.from_string(course_run.key)

        # NOTE: This serializer expects SearchQuerySet results, so we run a search on the newly-created object
        # to generate such a result.
        result = SearchQuerySet().models(CourseRun).filter(key=course_run.key)[0]
        serializer = CourseRunSearchSerializer(result)

        expected = {
            'transcript_languages': [self.serialize_language(l) for l in course_run.transcript_languages.all()],
            'short_description': course_run.short_description,
            'start': self.serialize_datetime(course_run.start),
            'end': self.serialize_datetime(course_run.end),
            'enrollment_start': self.serialize_datetime(course_run.enrollment_start),
            'enrollment_end': self.serialize_datetime(course_run.enrollment_end),
            'key': course_run.key,
            'marketing_url': course_run.marketing_url,
            'pacing_type': course_run.pacing_type,
            'language': self.serialize_language(course_run.language),
            'full_description': course_run.full_description,
            'title': course_run.title,
            'content_type': 'courserun',
            'org': course_run_key.org,
            'number': course_run_key.course,
            'seat_types': course_run.seat_types,
            'image_url': course_run.image_url,
            'type': course_run.type,
            'level_type': course_run.level_type.name,
            'availability': course_run.availability,
        }
        self.assertDictEqual(serializer.data, expected)


class ProgramSearchSerializerTests(TestCase):
    def test_data(self):
        program = ProgramFactory()
        authoring_organization, crediting_organization = OrganizationFactory.create_batch(2)
        program.authoring_organizations.add(authoring_organization)
        program.credit_backing_organizations.add(crediting_organization)
        program.save()
        expected_organizations = [
            OrganizationSerializer(org).data for org in (authoring_organization, crediting_organization)
        ]

        # NOTE: This serializer expects SearchQuerySet results, so we run a search on the newly-created object
        # to generate such a result.
        result = SearchQuerySet().models(Program).filter(uuid=program.uuid)[0]
        serializer = ProgramSearchSerializer(result)

        expected = {
            'uuid': str(program.uuid),
            'title': program.title,
            'subtitle': program.subtitle,
            'type': program.type.name,
            'marketing_url': program.marketing_url,
            'authoring_organizations': expected_organizations,
            'content_type': 'program',
            'card_image_url': program.card_image_url,
            'status': program.status,
        }
        self.assertDictEqual(serializer.data, expected)

    def test_organization_bodies_missing(self):
        program = ProgramFactory()

        result = SearchQuerySet().models(Program).filter(uuid=program.uuid)[0]
        result.organization_bodies = None
        serializer = ProgramSearchSerializer(result)

        expected = {
            'uuid': str(program.uuid),
            'title': program.title,
            'subtitle': program.subtitle,
            'type': program.type.name,
            'marketing_url': program.marketing_url,
            'authoring_organizations': [],
            'content_type': 'program',
            'card_image_url': program.card_image_url,
            'status': program.status,
        }
        self.assertDictEqual(serializer.data, expected)
