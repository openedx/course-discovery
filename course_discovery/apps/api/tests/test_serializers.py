from datetime import datetime

import ddt
from django.test import TestCase

from course_discovery.apps.api.serializers import(
    CatalogSerializer, CourseSerializer, CourseRunSerializer, ContainedCoursesSerializer, ImageSerializer,
    SubjectSerializer, PrerequisiteSerializer, VideoSerializer, OrganizationSerializer, SeatSerializer,
    PersonSerializer,
)
from course_discovery.apps.catalogs.tests.factories import CatalogFactory
from course_discovery.apps.core.tests.factories import UserFactory
from course_discovery.apps.course_metadata.tests.factories import (
    CourseFactory, CourseRunFactory, SubjectFactory, PrerequisiteFactory,
    ImageFactory, VideoFactory, OrganizationFactory, PersonFactory, SeatFactory
)


def json_date_format(datetime_obj):
    return datetime.strftime(datetime_obj, "%Y-%m-%dT%H:%M:%S.%fZ")


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


class CourseSerializerTests(TestCase):
    def test_data(self):
        course = CourseFactory()
        image = course.image
        video = course.video
        CourseRunFactory.create_batch(3, course=course)
        serializer = CourseSerializer(course)

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
            'course_runs': CourseRunSerializer(course.course_runs, many=True).data,
            'marketing_url': course.marketing_url
        }

        self.assertDictEqual(serializer.data, expected)


class CourseRunSerializerTests(TestCase):
    def test_data(self):
        course_run = CourseRunFactory()
        image = course_run.image
        video = course_run.video
        serializer = CourseRunSerializer(course_run)

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
            'modified': json_date_format(course_run.modified)  # pylint: disable=no-member
        }

        self.assertDictEqual(serializer.data, expected)


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
        image = organization.logo_image
        serializer = OrganizationSerializer(organization)

        expected = {
            'key': organization.key,
            'name': organization.name,
            'description': organization.description,
            'homepage_url': organization.homepage_url,
            'logo_image': {
                'src': image.src,
                'description': image.description,
                'height': image.height,
                'width': image.width
            }
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
        image = person.profile_image
        serializer = PersonSerializer(person)

        expected = {
            'key': person.key,
            'name': person.name,
            'title': person.title,
            'bio': person.bio,
            'profile_image': ImageSerializer(image).data
        }

        self.assertDictEqual(serializer.data, expected)
