import ddt
from django.test import TestCase

from course_discovery.apps.course_metadata.models import AbstractNamedModel, AbstractMediaModel
from course_discovery.apps.course_metadata.tests import factories


class CourseTests(TestCase):
    """ Tests for the `Course` model. """

    def test_str(self):
        """ Verify casting an instance to a string returns a string containing the key and title. """
        course = factories.CourseFactory()
        self.assertEqual(str(course), '{key}: {title}'.format(key=course.key, title=course.title))


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
        """ Verify casting an instance to a string returns a string containing the name. """

        class TestAbstractMediaModel(AbstractMediaModel):
            pass

        src = 'http://example.com/image.jpg'
        instance = TestAbstractMediaModel(src=src)
        self.assertEqual(str(instance), src)
