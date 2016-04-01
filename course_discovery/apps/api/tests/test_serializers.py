from datetime import datetime

import ddt
from django.core.urlresolvers import reverse
from django.test import TestCase, RequestFactory

from course_discovery.apps.api.serializers import(
    CatalogSerializer, CourseSerializer, CourseRunSerializer, ContainedCoursesSerializer, ImageSerializer,
    SubjectSerializer, PrerequisiteSerializer, VideoSerializer, OrganizationSerializer,
    EffortSerializer, SyllabusSerializer, SeatSerializer, PersonSerializer
)
from course_discovery.apps.catalogs.tests.factories import CatalogFactory
from course_discovery.apps.course_metadata.tests.factories import (
    CourseFactory, CourseRunFactory, SubjectFactory, PrerequisiteFactory,
    ImageFactory, VideoFactory, OrganizationFactory, PersonFactory, SyllabusFactory, SeatFactory
)


def json_date_format(datetime_obj):
    return datetime.strftime(datetime_obj, "%Y-%m-%dT%H:%M:%S.%fZ")


class CatalogSerializerTests(TestCase):
    def test_data(self):
        catalog = CatalogFactory()
        path = reverse('api:v1:catalog-detail', kwargs={'id': catalog.id})
        request = RequestFactory().get(path)
        serializer = CatalogSerializer(catalog, context={'request': request})

        expected = {
            'id': catalog.id,
            'name': catalog.name,
            'query': catalog.query,
            'url': request.build_absolute_uri(),
        }
        self.assertDictEqual(serializer.data, expected)


class CourseSerializerTests(TestCase):
    def test_data(self):
        course = CourseFactory()
        image = course.image
        video = course.video
        path = reverse('api:v1:course-detail', kwargs={'key': course.key})
        request = RequestFactory().get(path)
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
            'modified': json_date_format(course.modified)  # pylint: disable=no-member
        }

        self.assertDictEqual(serializer.data, expected)


class CourseRunSerializerTests(TestCase):
    def test_data(self):
        self.maxDiff = None
        course_run = CourseRunFactory()
        image = course_run.image
        video = course_run.video
        path = reverse('api:v1:course_run-detail', kwargs={'key': course_run.key})
        request = RequestFactory().get(path)
        serializer = CourseRunSerializer(course_run, context={'request': request})

        expected = {
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
            'effort': {
                'min': course_run.min_effort,
                'max': course_run.max_effort
            },
            'syllabus': None,
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


class EffortSerializerTests(TestCase):
    def test_data(self):
        course_run = CourseRunFactory()
        serializer = EffortSerializer(course_run)

        expected = {
            'min': course_run.min_effort,
            'max': course_run.max_effort
        }

        self.assertDictEqual(serializer.data, expected)


class SyllabusSerializerTests(TestCase):
    def test_data(self):
        syllabus = SyllabusFactory()
        title = SyllabusFactory(parent=syllabus)
        SyllabusFactory(parent=title)
        SyllabusFactory(parent=title)
        SyllabusFactory(parent=title)
        serializer = SyllabusSerializer(syllabus.children, many=True)  # pylint: disable=no-member

        expected = [
            {
                'title': title.value,
                'contents': [child.value for child in title.children.all()]  # pylint: disable=no-member
            }
        ]

        self.assertListEqual(serializer.data, expected)


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
            'name': person.name,
            'title': person.title,
            'bio': person.bio,
            'profile_image': ImageSerializer(image).data
        }

        self.assertDictEqual(serializer.data, expected)
