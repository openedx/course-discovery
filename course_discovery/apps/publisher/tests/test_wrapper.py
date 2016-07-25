# pylint: disable=no-member
from django.test import TestCase

from course_discovery.apps.course_metadata.tests.factories import CourseRunFactory, OrganizationFactory
from course_discovery.apps.course_metadata.models import CourseOrganization
from course_discovery.apps.publisher.wrappers import CourseRunWrapper


class CourseRunWrapperTests(TestCase):
    """ Tests for the publisher `BaseWrapper` model. """

    def setUp(self):
        super(CourseRunWrapperTests, self).setUp()
        self.course_run = CourseRunFactory()
        course = self.course_run.course
        organization_1 = OrganizationFactory()
        organization_2 = OrganizationFactory()
        CourseOrganization.objects.create(
            course=course,
            organization=organization_1,
            relation_type=CourseOrganization.OWNER
        )
        CourseOrganization.objects.create(
            course=course,
            organization=organization_2,
            relation_type=CourseOrganization.OWNER
        )
        course.save()

        self.wrapped_course_run = CourseRunWrapper(self.course_run)

    def test_title(self):
        """ Verify that the wrapper can override course_run title. """
        self.assertEqual(self.wrapped_course_run.title, self.course_run.course.title)

    def test_partner(self):
        """ Verify that the wrapper can return partner values. """
        partner = "/".join([org.key for org in self.course_run.course.organizations.all()])
        self.assertEqual(self.wrapped_course_run.partner, partner)

    def test_model_attr(self):
        """ Verify that the wrapper passes through object values not defined on wrapper. """
        self.assertEqual(self.wrapped_course_run.key, self.course_run.key)
