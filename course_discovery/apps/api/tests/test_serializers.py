from datetime import datetime

import ddt
from django.core.urlresolvers import reverse
from django.test import TestCase, RequestFactory

from course_discovery.apps.api.serializers import(
    CatalogSerializer, CourseSerializer, ContainedCoursesSerializer, ImageSerializer,
    SubjectSerializer, PrerequisiteSerializer, VideoSerializer, OrganizationSerializer
)
from course_discovery.apps.catalogs.tests.factories import CatalogFactory
from course_discovery.apps.course_metadata.tests.factories import (
    CourseFactory, SubjectFactory, PrerequisiteFactory, ImageFactory, VideoFactory, OrganizationFactory
)


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
            'image': {
                'src': image.src,
                'description': image.description,
                'height': image.height,
                'width': image.width
            },
            'video': {
                'src': video.src,
                'description': video.description,
                'image': {
                    'src': video.image.src,
                    'description': video.image.description,
                    'height': video.image.height,
                    'width': video.image.width
                }
            },
            'owners': [],
            'sponsors': [],
            'modified': datetime.strftime(course.modified, "%Y-%m-%dT%H:%M:%S.%fZ")
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
class LinkObjectSerializerTests(TestCase):
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
            'image': {
                'src': image.src,
                'description': image.description,
                'height': image.height,
                'width': image.width
            }
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
