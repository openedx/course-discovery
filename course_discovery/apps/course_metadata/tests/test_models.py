import datetime

import ddt
from django.db import IntegrityError
import mock
import pytz
from django.conf import settings
from django.test import TestCase

from course_discovery.apps.core.utils import SearchQuerySetWrapper
from course_discovery.apps.course_metadata.models import (
    AbstractNamedModel, AbstractMediaModel, AbstractValueModel, CourseOrganization, Course, CourseRun
)
from course_discovery.apps.course_metadata.tests import factories


# pylint: disable=no-member

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
        owners = self.course.owners
        self.assertEqual(len(owners), 1)
        self.assertEqual(owners[0], self.owner)

    def test_sponsors(self):
        """ Verify that the sponsors property returns only sponsor related organizations. """
        sponsors = self.course.sponsors
        self.assertEqual(len(sponsors), 1)
        self.assertEqual(sponsors[0], self.sponsor)

    def test_active_course_runs(self):
        """ Verify the property returns only course runs currently open for enrollment or opening in the future. """
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

    def test_seat_types(self):
        """ Verify the property returns a list of all seat types associated with the course run. """
        self.assertEqual(self.course_run.seat_types, [])

        seats = factories.SeatFactory.create_batch(3, course_run=self.course_run)
        expected = sorted([seat.type for seat in seats])
        self.assertEqual(sorted(self.course_run.seat_types), expected)

    def test_image_url(self):
        """ Verify the property returns the associated image's URL. """
        self.assertEqual(self.course_run.image_url, self.course_run.image.src)

        self.course_run.image = None
        self.assertIsNone(self.course_run.image)
        self.assertIsNone(self.course_run.image_url)

    @ddt.data(
        ('obviously-wrong', None,),
        (('audit',), 'audit',),
        (('honor',), 'honor',),
        (('credit', 'verified', 'audit',), 'credit',),
        (('verified', 'honor',), 'verified',),
        (('professional',), 'professional',),
        (('no-id-professional',), 'professional',),
    )
    @ddt.unpack
    def test_type(self, seat_types, expected_course_run_type):
        """ Verify the property returns the appropriate type string for the CourseRun. """
        for seat_type in seat_types:
            factories.SeatFactory(course_run=self.course_run, type=seat_type)
        self.assertEqual(self.course_run.type, expected_course_run_type)

    def assert_course_run_has_no_type(self, course_run, expected_seats):
        """ Asserts the given CourseRun has no type value, and a message is logged to that effect. """
        with mock.patch('course_discovery.apps.course_metadata.models.logger') as mock_logger:
            self.assertEqual(course_run.type, None)
            mock_logger.warning.assert_called_with(
                'Unable to determine type for course run [%s]. Seat types are [%s]',
                course_run.key,
                expected_seats
            )

    def test_type_with_unknown_seat_type(self):
        """ Verify the property logs a warning if the CourseRun has no Seats or the Seats have an unknown seat type. """
        self.assert_course_run_has_no_type(self.course_run, set())

        seat_type = 'super-wrong'
        factories.SeatFactory(course_run=self.course_run, type=seat_type)
        self.assert_course_run_has_no_type(self.course_run, set([seat_type]))


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


class ProgramTests(TestCase):
    """Tests of the Program model."""

    def test_str(self):
        """Verify that a program is properly converted to a str."""
        program = factories.ProgramFactory()
        self.assertEqual(str(program), program.name)

    def test_marketing_url(self):
        """ Verify the property creates a complete marketing URL. """
        program = factories.ProgramFactory()
        expected = '{root}/{category}/{slug}'.format(root=settings.MARKETING_URL_ROOT.strip('/'),
                                                     category=program.category, slug=program.marketing_slug)
        self.assertEqual(program.marketing_url, expected)

    def test_marketing_url_without_slug(self):
        """ Verify the property returns None if the Program has no marketing_slug set. """
        program = factories.ProgramFactory(marketing_slug='')
        self.assertIsNone(program.marketing_url)


class PersonSocialNetworkTests(TestCase):
    """Tests of the PersonSocialNetwork model."""
    def setUp(self):
        super(PersonSocialNetworkTests, self).setUp()
        self.network = factories.PersonSocialNetworkFactory()
        self.person = factories.PersonFactory()

    def test_str(self):
        """Verify that a person-social-network is properly converted to a str."""
        self.assertEqual(
            str(self.network), '{type}: {value}'.format(type=self.network.type, value=self.network.value)
        )

    def test_unique_constraint(self):
        """Verify that a person-social-network does not allow multiple accounts for same
        social network.
        """
        factories.PersonSocialNetworkFactory(person=self.person, type='facebook')
        with self.assertRaises(IntegrityError):
            factories.PersonSocialNetworkFactory(person=self.person, type='facebook')


class CourseSocialNetworkTests(TestCase):
    """Tests of the CourseSocialNetwork model."""
    def setUp(self):
        super(CourseSocialNetworkTests, self).setUp()
        self.network = factories.CourseRunSocialNetworkFactory()
        self.course_run = factories.CourseRunFactory()

    def test_str(self):
        """Verify that a course-social-network is properly converted to a str."""
        self.assertEqual(
            str(self.network), '{type}: {value}'.format(type=self.network.type, value=self.network.value)
        )

    def test_unique_constraint(self):
        """Verify that a course-social-network does not allow multiple accounts for same
        social network.
        """
        factories.CourseRunSocialNetworkFactory(course_run=self.course_run, type='facebook')
        with self.assertRaises(IntegrityError):
            factories.CourseRunSocialNetworkFactory(course_run=self.course_run, type='facebook')
