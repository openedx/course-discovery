from unittest import skip

from django.test import TestCase, override_settings

from course_discovery.apps.core.tests.mixins import ElasticsearchTestMixin

ACCESS_TOKEN = 'secret'
COURSES_API_URL = 'https://lms.example.com/api/courses/v1'
ECOMMERCE_API_URL = 'https://ecommerce.example.com/api/v2'
JSON = 'application/json'


@skip('Skip until search has been resolved')
@override_settings(ECOMMERCE_API_URL=ECOMMERCE_API_URL, COURSES_API_URL=COURSES_API_URL)
class CourseTests(ElasticsearchTestMixin, TestCase):
    pass
