import datetime

import ddt
import pytz
from django.test import TestCase

from course_discovery.apps.core.utils import SearchQuerySetWrapper
from course_discovery.apps.course_metadata.models import (
    AbstractNamedModel, AbstractMediaModel, AbstractValueModel, CourseOrganization, Course, CourseRun
)
from course_discovery.apps.course_metadata.tests import factories


class CourseTests(TestCase):
    """ Tests for the `Course` model. """

    def setUp(self):
        super(CourseTests, self).setUp()
        self.course = factories.CourseFactory()
        self.owner = factories.OrganizationFactory()
        self.sponsor = factories.OrganizationFactory()
        CourseOrganization.objects.create(
            course=self.course,
            organization=self.owner,
            relation_type=CourseOrganization.OWNER
        )
        CourseOrganization.objects.create(
            course=self.course,
            organization=self.sponsor,
            relation_type=CourseOrganization.SPONSOR
        )

    def test_str(self):
        """ Verify casting an instance to a string returns a string containing the key and title. """
        self.assertEqual(str(self.course), '{key}: {title}'.format(key=self.course.key, title=self.course.title))

    def test_owners(self):
        """ Verify that the owners property returns only owner related organizations. """
        owners = self.course.owners  # pylint: disable=no-member
        self.assertEqual(len(owners), 1)
        self.assertEqual(owners[0], self.owner)

    def test_sponsors(self):
        """ Verify that the sponsors property returns only sponsor related organizations. """
        sponsors = self.course.sponsors  # pylint: disable=no-member
        self.assertEqual(len(sponsors), 1)
        self.assertEqual(sponsors[0], self.sponsor)

    def test_active_course_runs(self):
        """ Verify the property returns only course runs currently open for enrollment or opening in the future. """
        # pylint: disable=no-member
        self.assertListEqual(list(self.course.active_course_runs), [])

        # Create course with end date in future and enrollment_end in past.
        end = datetime.datetime.now(pytz.UTC) + datetime.timedelta(days=2)
        enrollment_end = datetime.datetime.now(pytz.UTC) - datetime.timedelta(days=1)
        factories.CourseRunFactory(course=self.course, end=end, enrollment_end=enrollment_end)

        # Create course with end date in past and no enrollment_end.
        end = datetime.datetime.now(pytz.UTC) - datetime.timedelta(days=2)
        factories.CourseRunFactory(course=self.course, end=end, enrollment_end=None)

        self.assertListEqual(list(self.course.active_course_runs), [])

        # Create course with end date in future and enrollment_end in future.
        end = datetime.datetime.now(pytz.UTC) + datetime.timedelta(days=2)
        enrollment_end = datetime.datetime.now(pytz.UTC) + datetime.timedelta(days=1)
        active_enrollment_end = factories.CourseRunFactory(course=self.course, end=end, enrollment_end=enrollment_end)

        # Create course with end date in future and no enrollment_end.
        active_no_enrollment_end = factories.CourseRunFactory(course=self.course, end=end, enrollment_end=None)

        self.assertEqual(set(self.course.active_course_runs), {active_enrollment_end, active_no_enrollment_end})

    def test_search(self):
        """ Verify the method returns a filtered queryset of courses. """
        title = 'Some random title'
        courses = factories.CourseFactory.create_batch(3, title=title)
        courses = sorted(courses, key=lambda course: course.key)
        query = 'title:' + title
        actual = list(Course.search(query).order_by('key'))
        self.assertEqual(actual, courses)


@ddt.ddt
class CourseRunTests(TestCase):
    """ Tests for the `CourseRun` model. """

    def setUp(self):
        super(CourseRunTests, self).setUp()
        self.course_run = factories.CourseRunFactory()

    def test_str(self):
        """ Verify casting an instance to a string returns a string containing the key and title. """
        course_run = self.course_run
        # pylint: disable=no-member
        self.assertEqual(str(course_run), '{key}: {title}'.format(key=course_run.key, title=course_run.title))

    @ddt.data('title', 'short_description', 'full_description')
    def test_override_fields(self, field_name):
        """ Verify the `CourseRun`'s override field overrides the related `Course`'s field. """
        override_field_name = "{}_override".format(field_name)
        self.assertIsNone(getattr(self.course_run, override_field_name))
        self.assertEqual(getattr(self.course_run, field_name), getattr(self.course_run.course, field_name))

        # Setting the property to a non-empty value should set the override field,
        # and trigger the field property getter to use the override.
        override_text = 'A Better World'
        setattr(self.course_run, field_name, override_text)
        self.assertEqual(getattr(self.course_run, override_field_name), override_text)
        self.assertEqual(getattr(self.course_run, field_name), override_text)

        # Setting the title property to an empty value should set the title_override field to None,
        # and trigger the title property getter to use the title of the parent course.
        setattr(self.course_run, field_name, None)
        self.assertIsNone(getattr(self.course_run, override_field_name))
        self.assertEqual(getattr(self.course_run, field_name), getattr(self.course_run.course, field_name))

    def test_search(self):
        """ Verify the method returns a filtered queryset of course runs. """
        title = 'Some random title'
        course_runs = factories.CourseRunFactory.create_batch(3, title=title)
        query = 'title:' + title
        actual_sorted = sorted(SearchQuerySetWrapper(CourseRun.search(query)), key=lambda course_run: course_run.key)
        expected_sorted = sorted(course_runs, key=lambda course_run: course_run.key)
        self.assertEqual(actual_sorted, expected_sorted)


class OrganizationTests(TestCase):
    """ Tests for the `Organization` model. """

    def test_str(self):
        """ Verify casting an instance to a string returns a string containing the key and name. """
        organization = factories.OrganizationFactory()
        self.assertEqual(str(organization), '{key}: {name}'.format(key=organization.key, name=organization.name))


class PersonTests(TestCase):
    """ Tests for the `Person` model. """

    def test_str(self):
        """ Verify casting an instance to a string returns a string containing the key and name. """
        person = factories.PersonFactory()
        self.assertEqual(str(person), '{key}: {name}'.format(key=person.key, name=person.name))


class AbstractNamedModelTests(TestCase):
    """ Tests for AbstractNamedModel. """

    def test_str(self):
        """ Verify casting an instance to a string returns a string containing the name. """

        class TestAbstractNamedModel(AbstractNamedModel):
            pass

        name = 'abc'
        instance = TestAbstractNamedModel(name=name)
        self.assertEqual(str(instance), name)


class AbstractMediaModelTests(TestCase):
    """ Tests for AbstractMediaModel. """

    def test_str(self):
        """ Verify casting an instance to a string returns a string containing the src. """

        class TestAbstractMediaModel(AbstractMediaModel):
            pass

        src = 'http://example.com/image.jpg'
        instance = TestAbstractMediaModel(src=src)
        self.assertEqual(str(instance), src)


class AbstractValueModelTests(TestCase):
    """ Tests for AbstractValueModel. """

    def test_str(self):
        """ Verify casting an instance to a string returns a string containing the value. """

        class TestAbstractValueModel(AbstractValueModel):
            pass

        value = 'abc'
        instance = TestAbstractValueModel(value=value)
        self.assertEqual(str(instance), value)
