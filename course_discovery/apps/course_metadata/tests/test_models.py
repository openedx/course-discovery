import datetime
import itertools
from decimal import Decimal

import ddt
import pytz
from dateutil.parser import parse
from django.conf import settings
from django.db import IntegrityError
from django.test import TestCase
from freezegun import freeze_time

from course_discovery.apps.core.models import Currency
from course_discovery.apps.core.tests.helpers import make_image_file
from course_discovery.apps.core.utils import SearchQuerySetWrapper
from course_discovery.apps.course_metadata.models import (
    AbstractNamedModel, AbstractMediaModel, AbstractValueModel, Course, CourseRun, SeatType,
)
from course_discovery.apps.course_metadata.tests import factories
from course_discovery.apps.course_metadata.tests.factories import CourseRunFactory
from course_discovery.apps.ietf_language_tags.models import LanguageTag


# pylint: disable=no-member


class CourseTests(TestCase):
    """ Tests for the `Course` model. """

    def setUp(self):
        super(CourseTests, self).setUp()
        self.course = factories.CourseFactory()

    def test_str(self):
        """ Verify casting an instance to a string returns a string containing the key and title. """
        self.assertEqual(str(self.course), '{key}: {title}'.format(key=self.course.key, title=self.course.title))

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

    def test_level_type(self):
        """ Verify the property returns the associated Course's level type. """
        self.assertEqual(self.course_run.level_type, self.course_run.course.level_type)

    @freeze_time('2016-06-21 00:00:00Z')
    @ddt.data(
        (None, None, 'Upcoming'),
        ('2030-01-01 00:00:00Z', None, 'Upcoming'),
        (None, '2016-01-01 00:00:00Z', 'Archived'),
        ('2015-01-01 00:00:00Z', '2016-01-01 00:00:00Z', 'Archived'),
        ('2016-01-01 00:00:00Z', '2017-01-01 00:00:00Z', 'Current'),
        ('2016-07-21 00:00:00Z', '2017-01-01 00:00:00Z', 'Starting Soon'),
    )
    @ddt.unpack
    def test_availability(self, start, end, expected_availability):
        """ Verify the property returns the appropriate availability string based on the start/end dates. """
        if start:
            start = parse(start)

        if end:
            end = parse(end)
        course_run = factories.CourseRunFactory(start=start, end=end)
        self.assertEqual(course_run.availability, expected_availability)


class OrganizationTests(TestCase):
    """ Tests for the `Organization` model. """

    def test_str(self):
        """ Verify casting an instance to a string returns a string containing the key and name. """
        organization = factories.OrganizationFactory()
        self.assertEqual(str(organization), '{key}: {name}'.format(key=organization.key, name=organization.name))


class PersonTests(TestCase):
    """ Tests for the `Person` model. """

    def setUp(self):
        super(PersonTests, self).setUp()
        self.person = factories.PersonFactory()

    def test_full_name(self):
        """ Verify the property returns the person's full name. """
        expected = self.person.given_name + ' ' + self.person.family_name
        self.assertEqual(self.person.full_name, expected)

    def test_str(self):
        """ Verify casting an instance to a string returns the person's full name. """
        self.assertEqual(str(self.person), self.person.full_name)


class PositionTests(TestCase):
    """ Tests for the `Position` model. """

    def setUp(self):
        super(PositionTests, self).setUp()
        self.position = factories.PositionFactory()

    def test_organization_name(self):
        """ Verify the property returns the name of the related Organization or the overridden value. """
        self.assertEqual(self.position.organization_name, self.position.organization.name)

        self.position.organization_override = 'ACME'
        self.assertEqual(self.position.organization_name, self.position.organization_override)

    def test_str(self):
        """ Verify casting an instance to a string returns the title and organization. """
        expected = self.position.title + ' at ' + self.position.organization_name
        self.assertEqual(str(self.position), expected)


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

    def setUp(self):
        super(ProgramTests, self).setUp()
        transcript_languages = LanguageTag.objects.all()[:2]
        subjects = factories.SubjectFactory.create_batch(2)
        self.course_runs = factories.CourseRunFactory.create_batch(
            3, transcript_languages=transcript_languages, course__subjects=subjects)
        self.courses = [course_run.course for course_run in self.course_runs]
        self.excluded_course_run = factories.CourseRunFactory(course=self.courses[0])
        self.program = factories.ProgramFactory(courses=self.courses, excluded_course_runs=[self.excluded_course_run])

    def test_str(self):
        """Verify that a program is properly converted to a str."""
        self.assertEqual(str(self.program), self.program.title)

    def test_marketing_url(self):
        """ Verify the property creates a complete marketing URL. """
        expected = '{root}/{type}/{slug}'.format(root=self.program.partner.marketing_site_url_root.strip('/'),
                                                 type=self.program.type.name.lower(), slug=self.program.marketing_slug)
        self.assertEqual(self.program.marketing_url, expected)

    def test_marketing_url_without_slug(self):
        """ Verify the property returns None if the Program has no marketing_slug set. """
        self.program.marketing_slug = ''
        self.assertIsNone(self.program.marketing_url)

    def test_course_runs(self):
        """
        Verify that we only fetch course runs for the program, and not other course runs for other programs and that the
        property returns the set of associated CourseRuns minus those that are explicitly excluded.
        """
        course_run = factories.CourseRunFactory()
        factories.ProgramFactory(courses=[course_run.course])
        # Verify that course run is not returned in set
        self.assertEqual(set(self.program.course_runs), set(self.course_runs))

    def test_languages(self):
        expected_languages = set([course_run.language for course_run in self.course_runs])
        actual_languages = self.program.languages
        self.assertGreater(len(actual_languages), 0)
        self.assertEqual(actual_languages, expected_languages)

    def test_transcript_languages(self):
        expected_transcript_languages = itertools.chain.from_iterable(
            [list(course_run.transcript_languages.all()) for course_run in self.course_runs])
        expected_transcript_languages = set(expected_transcript_languages)
        actual_transcript_languages = self.program.transcript_languages

        self.assertGreater(len(actual_transcript_languages), 0)
        self.assertEqual(actual_transcript_languages, expected_transcript_languages)

    def test_subjects(self):
        expected_subjects = itertools.chain.from_iterable([list(course.subjects.all()) for course in self.courses])
        expected_subjects = set(expected_subjects)
        actual_subjects = self.program.subjects

        self.assertGreater(len(actual_subjects), 0)
        self.assertEqual(actual_subjects, expected_subjects)

    def test_start(self):
        """ Verify the property returns the minimum start date for the course runs associated with the
        program's courses. """
        expected_start = min([course_run.start for course_run in self.course_runs])
        self.assertEqual(self.program.start, expected_start)

        # Verify start is None for programs with no courses.
        self.program.courses.clear()
        self.assertIsNone(self.program.start)

        # Verify start is None if no course runs have a start date.
        course_run = CourseRunFactory(start=None)
        self.program.courses.add(course_run.course)
        self.assertIsNone(self.program.start)

    def test_price_ranges(self):
        currency = Currency.objects.get(code='USD')
        course_run = factories.CourseRunFactory()
        factories.SeatFactory(type='audit', currency=currency, course_run=course_run, price=0)
        factories.SeatFactory(type='credit', currency=currency, course_run=course_run, price=600)
        factories.SeatFactory(type='verified', currency=currency, course_run=course_run, price=100)
        applicable_seat_types = SeatType.objects.filter(slug__in=['credit', 'verified'])
        program_type = factories.ProgramTypeFactory(applicable_seat_types=applicable_seat_types)
        program = factories.ProgramFactory(type=program_type, courses=[course_run.course])

        expected_price_ranges = [{'currency': 'USD', 'min': Decimal(100), 'max': Decimal(600)}]
        self.assertEqual(program.price_ranges, expected_price_ranges)

    def test_staff(self):
        staff = factories.PersonFactory.create_batch(2)
        self.course_runs[0].staff.add(staff[0])
        self.course_runs[1].staff.add(staff[1])

        self.assertEqual(self.program.staff, set(staff))

    def test_banner_image(self):
        self.program.banner_image = make_image_file('test_banner.jpg')
        self.program.save()
        image_url_prefix = '{}media/programs/banner_images/'.format(settings.MEDIA_URL)
        self.assertIn(image_url_prefix, self.program.banner_image.url)
        for size_key in self.program.banner_image.field.variations:
            # Get different sizes specs from the model field
            # Then get the file path from the available files
            sized_file = getattr(self.program.banner_image, size_key, None)
            self.assertIsNotNone(sized_file)
            self.assertIn(image_url_prefix, sized_file.url)


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


class SeatTypeTests(TestCase):
    """ Tests of the SeatType model. """

    def test_str(self):
        seat_type = factories.SeatTypeFactory()
        self.assertEqual(str(seat_type), seat_type.name)


class ProgramTypeTests(TestCase):
    """ Tests of the ProgramType model. """

    def test_str(self):
        program_type = factories.ProgramTypeFactory()
        self.assertEqual(str(program_type), program_type.name)
