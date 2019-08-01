import uuid
from re import escape

import ddt
import mock
import pytest
from django.apps import apps
from django.core.exceptions import ValidationError
from django.test import TestCase
from factory import DjangoModelFactory
from testfixtures import LogCapture
from waffle.testutils import override_switch

from course_discovery.apps.api.v1.tests.test_views.mixins import FuzzyInt
from course_discovery.apps.core.models import Currency
from course_discovery.apps.course_metadata.models import (
    CourseRun, Curriculum, CurriculumCourseMembership, DataLoaderConfig, DeletePersonDupsConfig,
    DrupalPublishUuidConfig, MigratePublisherToCourseMetadataConfig, ProfileImageDownloadConfig, ProgramType, Seat,
    SubjectTranslation, TagCourseUuidsConfig, TopicTranslation
)
from course_discovery.apps.course_metadata.signals import _duplicate_external_key_message
from course_discovery.apps.course_metadata.tests import factories

LOGGER_NAME = 'course_discovery.apps.course_metadata.signals'


@pytest.mark.django_db
@mock.patch('course_discovery.apps.api.cache.set_api_timestamp')
class TestCacheInvalidation:
    def test_model_change(self, mock_set_api_timestamp):
        """
        Verify that the API cache is invalidated after course_metadata models
        are saved or deleted.
        """
        factory_map = {}
        for factorylike in factories.__dict__.values():
            if isinstance(factorylike, type) and issubclass(factorylike, DjangoModelFactory):
                if getattr(factorylike, '_meta', None) and factorylike._meta.model:
                    factory_map[factorylike._meta.model] = factorylike

        # These are the models whose post_save and post_delete signals we're
        # connecting to. We want to test each of them.
        for model in apps.get_app_config('course_metadata').get_models():
            # Ignore models that aren't exposed by the API or are only used for testing.
            if model in [DataLoaderConfig, DeletePersonDupsConfig, DrupalPublishUuidConfig,
                         MigratePublisherToCourseMetadataConfig, SubjectTranslation, TopicTranslation,
                         ProfileImageDownloadConfig, TagCourseUuidsConfig]:
                continue
            if 'abstract' in model.__name__.lower() or 'historical' in model.__name__.lower():
                continue

            factory = factory_map.get(model)
            if not factory:
                pytest.fail('The {} model is missing a factory.'.format(model))

            # Verify that model creation and deletion invalidates the API cache.
            instance = factory()

            assert mock_set_api_timestamp.called
            mock_set_api_timestamp.reset_mock()

            instance.delete()

            assert mock_set_api_timestamp.called
            mock_set_api_timestamp.reset_mock()


class SeatSignalsTests(TestCase):
    """ Tests for the signal to save seats model into database """
    def setUp(self):
        super().setUp()
        self.course_runs = factories.CourseRunFactory.create_batch(3)
        self.partner = factories.PartnerFactory()
        self.course = self.course_runs[0].course
        self.course.partner = self.partner
        self.course_run = self.course_runs[0]
        self.program_type = ProgramType.objects.get(slug='masters')
        self.degree = factories.DegreeFactory(courses=[self.course], type=self.program_type, partner=self.partner)
        self.currency = Currency.objects.get(code='USD')
        self.curriculum = Curriculum.objects.create(program=self.degree, uuid=uuid.uuid4())
        self.curriculum_course = factories.CurriculumCourseMembershipFactory(
            curriculum=self.curriculum,
            course=self.course
        )

    @override_switch('masters_course_mode_enabled', active=False)
    @mock.patch('course_discovery.apps.core.models.OAuthAPIClient')
    def test_seat_post_save_waffle_inactive(self, mock_client_init):
        mock_client = mock_client_init.return_value

        Seat.objects.create(
            course_run=self.course_run,
            type=Seat.MASTERS,
            currency=self.currency
        )

        self.assertFalse(mock_client.get.called)

    @override_switch('masters_course_mode_enabled', active=True)
    @mock.patch('course_discovery.apps.core.models.OAuthAPIClient')
    def test_seat_post_save_waffle_flag_active(self, mock_client_init):
        mock_client = mock_client_init.return_value

        created_seat = Seat.objects.create(
            course_run=self.course_run,
            type=Seat.MASTERS,
            currency=self.currency
        )

        course_run_key = self.course_run.key
        expected_call_url = self.partner.lms_coursemode_api_url + 'courses/{}/'.format(course_run_key)
        expected_call_data = {
            'course_id': created_seat.course_run.key,
            'mode_slug': created_seat.type,
            'mode_display_name': created_seat.type.capitalize(),
            'currency': str(created_seat.currency.code) if created_seat.currency else '',
            'min_price': int(created_seat.price),
        }

        mock_client.post.assert_called_with(expected_call_url, json=expected_call_data)

    @override_switch('masters_course_mode_enabled', active=True)
    @mock.patch('course_discovery.apps.core.models.OAuthAPIClient')
    def test_seat_already_exists_waffle_flag_active(self, mock_client_init):
        mock_client = mock_client_init.return_value
        course_run_key = self.course_run.key
        mock_client.get.return_value.json.return_value = [
            {
                'course_id': course_run_key,
                'mode_slug': Seat.MASTERS
            }
        ]

        with LogCapture(LOGGER_NAME) as log:
            created_seat = Seat.objects.create(
                course_run=self.course_run,
                type=Seat.MASTERS,
                currency=self.currency
            )

            self.assertTrue(mock_client.get.called)
            self.assertFalse(mock_client.post.called)
            log.check(
                (
                    LOGGER_NAME,
                    'INFO',
                    'Creating [{}] track on LMS for [{}] while it already have the track.'.format(
                        created_seat.type,
                        course_run_key
                    )
                )
            )

    @override_switch('masters_course_mode_enabled', active=True)
    @mock.patch('course_discovery.apps.core.models.OAuthAPIClient')
    def test_seat_post_save_waffle_flag_active_bad_response(self, mock_client_init):
        mock_client = mock_client_init.return_value
        course_run_key = self.course_run.key
        mock_client.get.return_value.data = []
        mock_client.post.return_value.ok = False

        with LogCapture(LOGGER_NAME) as log:
            created_seat = Seat.objects.create(
                course_run=self.course_run,
                type=Seat.MASTERS,
                currency=self.currency
            )
            log.check(
                (
                    LOGGER_NAME,
                    'ERROR',
                    'Failed to add [{}] course_mode to course_run [{}] in course_mode api to LMS.'.format(
                        created_seat.type,
                        course_run_key
                    )
                )
            )

    @override_switch('masters_course_mode_enabled', active=True)
    @mock.patch('course_discovery.apps.core.models.OAuthAPIClient')
    def test_seat_post_save_empty_lms_url(self, mock_client_init):
        mock_client = mock_client_init.return_value
        self.partner.lms_url = ''
        self.partner.save()

        with LogCapture(LOGGER_NAME) as log:
            Seat.objects.create(
                course_run=self.course_run,
                type=Seat.MASTERS,
                currency=self.currency
            )

            self.assertFalse(mock_client.get.called)
            log.check(
                (
                    LOGGER_NAME,
                    'INFO',
                    'LMS api client is not initiated. Cannot publish [{}] track for [{}] course_run'.format(
                        Seat.MASTERS,
                        self.course_run.key
                    )
                )
            )

    @override_switch('masters_course_mode_enabled', active=True)
    @mock.patch('course_discovery.apps.core.models.OAuthAPIClient')
    def test_seat_post_save_empty_coursemode_api_url(self, mock_client_init):
        mock_client = mock_client_init.return_value
        self.partner.lms_coursemode_api_url = ''
        self.partner.save()

        with LogCapture(LOGGER_NAME) as log:
            Seat.objects.create(
                course_run=self.course_run,
                type=Seat.MASTERS,
                currency=self.currency
            )

            self.assertFalse(mock_client.get.called)
            log.check(
                (
                    LOGGER_NAME,
                    'INFO',
                    'No lms coursemode api url configured. Masters seat for course_run [{}] not published'.format(
                        self.course_run.key
                    ),
                )
            )


class CurriculumCourseMembershipTests(TestCase):
    """ Tests of the CurriculumCourseMembership model """
    def setUp(self):
        super().setUp()
        self.course_runs = factories.CourseRunFactory.create_batch(3)
        self.course = self.course_runs[0].course
        self.program_type = ProgramType.objects.get(slug='masters')
        self.partner = factories.PartnerFactory()
        self.degree = factories.DegreeFactory(courses=[self.course], type=self.program_type, partner=self.partner)
        self.curriculum = Curriculum.objects.create(program=self.degree, uuid=uuid.uuid4())

    @override_switch('masters_course_mode_enabled', active=False)
    def test_course_curriculum_membership_side_effect_flag_inactive(self):

        CurriculumCourseMembership.objects.create(
            course=self.course,
            curriculum=self.curriculum
        )

        for course_run in self.course_runs:
            for seat in course_run.seats.all():
                self.assertNotEqual(seat.type, Seat.MASTERS)

    @override_switch('masters_course_mode_enabled', active=True)
    def test_course_curriculum_membership_side_effect_flag_active(self):
        with mock.patch('course_discovery.apps.core.models.OAuthAPIClient'):
            CurriculumCourseMembership.objects.create(
                course=self.course,
                curriculum=self.curriculum
            )

            for course_run in self.course_runs:
                for seat in course_run.seats.all():
                    self.assertEqual(seat.type, Seat.MASTERS)

    @override_switch('masters_course_mode_enabled', active=True)
    def test_course_curriculum_membership_side_effect_not_masters(self):
        self.program_type.slug = 'not_masters'
        self.program_type.save()

        CurriculumCourseMembership.objects.create(
            course=self.course,
            curriculum=self.curriculum
        )

        for course_run in self.course_runs:
            for seat in course_run.seats.all():
                self.assertNotEqual(seat.type, Seat.MASTERS)


class ExternalCourseKeyTestMixin(object):

    @staticmethod
    def _add_courses_to_curriculum(curriculum, *courses):
        for course in courses:
            factories.CurriculumCourseMembershipFactory(
                course=course,
                curriculum=curriculum
            )

    @staticmethod
    def _create_course_and_runs(course_identifier=1):
        course_name = 'course-{}'.format(course_identifier)
        course = factories.CourseFactory(
            key='course-id/' + course_name + '/test',
            title=course_name,
        )
        for course_run_letter in ('a', 'b', 'c'):
            course_run_name = course_name + course_run_letter
            factories.CourseRunFactory(
                course=course,
                key='course-run-id/' + course_run_name + '/test',
                external_key='ext-key-' + course_run_name,
            )
        return course

    @staticmethod
    def _create_single_course_curriculum(external_key, curriculum_name,):
        course_run = factories.CourseRunFactory(
            external_key=external_key
        )
        curriculum = factories.CurriculumFactory(
            name=curriculum_name,
            program=None,
        )
        factories.CurriculumCourseMembershipFactory(
            course=course_run.course,
            curriculum=curriculum,
        )
        return course_run, curriculum


class ExternalCourseKeyTestDataMixin(ExternalCourseKeyTestMixin):

    @classmethod
    def setUpTestData(cls):
        """
        Sets up the tree for testing external course keys

        program          1         2
                        / \\       |
        curriculum    1    2      3
                      |     \\   / \\
        course        1        2     3
        """
        super().setUpTestData()
        cls.program_1 = factories.ProgramFactory(title='program_1')
        cls.program_2 = factories.ProgramFactory(title='program_2')
        cls.programs = [None, cls.program_1, cls.program_2]
        cls.course_1 = cls._create_course_and_runs(1)
        cls.course_2 = cls._create_course_and_runs(2)
        cls.course_3 = cls._create_course_and_runs(3)
        cls.curriculum_1 = factories.CurriculumFactory(
            name='curriculum_1',
            program=cls.program_1,
        )
        cls.curriculum_2 = factories.CurriculumFactory(
            name='curriculum_2',
            program=cls.program_1,
        )
        cls.curriculum_3 = factories.CurriculumFactory(
            name='curriculum_3',
            program=cls.program_2,
        )
        cls.curriculums = [None, cls.curriculum_1, cls.curriculum_2, cls.curriculum_3]
        cls._add_courses_to_curriculum(cls.curriculum_1, cls.course_1)
        cls._add_courses_to_curriculum(cls.curriculum_2, cls.course_2)
        cls._add_courses_to_curriculum(cls.curriculum_3, cls.course_2, cls.course_3)


@ddt.ddt
class ExternalCourseKeySingleCollisionTests(ExternalCourseKeyTestDataMixin, TestCase):
    """
    There are currently three scenarios that can cause CourseRuns to have conflicting external_keys:
        1) Two Course Runs in the same Course
        2) Two Course Runs in different Courses but in the same Curriculum
        3) Two Course Runs in differenct Courses and Curricula but the same Program
    """

    @ddt.data(
        'course-run-id/course-2a/test',  # Scenario 1, within the same Course
        'course-run-id/course-3a/test',  # Scenario 2, within the same Curriculum
        'course-run-id/course-1a/test',  # Scenario 3, within the same Program
    )
    def test_create_course_run(self, copy_key):
        copied_course_run = CourseRun.objects.get(key=copy_key)
        message = _duplicate_external_key_message([copied_course_run])
        # This number may seem high but only 2 are select statements caused by the external key signal
        with self.assertNumQueries(8):
            with self.assertRaisesRegex(ValidationError, escape(message)):  # pylint: disable=deprecated-method
                factories.CourseRunFactory(
                    course=self.course_2,
                    external_key=copied_course_run.external_key,
                )

    @ddt.data(
        'course-run-id/course-2b/test',  # Scenario 1, within the same Course
        'course-run-id/course-3a/test',  # Scenario 2, within the same Curriculum
        'course-run-id/course-1a/test',  # Scenario 3, within the same Program
    )
    def test_modify_course_run(self, copy_key):
        copied_course_run = CourseRun.objects.get(key=copy_key)
        message = _duplicate_external_key_message([copied_course_run])
        course_run = CourseRun.objects.get(key='course-run-id/course-2a/test')
        # This number may seem high but only 3 are select statements caused by the external key signal
        with self.assertNumQueries(9):
            with self.assertRaisesRegex(ValidationError, escape(message)):  # pylint: disable=deprecated-method
                course_run.external_key = copied_course_run.external_key
                course_run.save()

    @ddt.data(
        1,  # Scenario 2, within the same Curriculum
        2,  # Scenaario 3, within the same Program
    )
    def test_create_curriculum_course_membership(self, curriculum_id):
        new_course_run = factories.CourseRunFactory(
            external_key='ext-key-course-1a'
        )
        new_course = new_course_run.course
        course_run_1a = CourseRun.objects.get(key='course-run-id/course-1a/test')
        message = _duplicate_external_key_message([course_run_1a])
        with self.assertNumQueries(2):
            with self.assertRaisesRegex(ValidationError, escape(message)):  # pylint: disable=deprecated-method
                factories.CurriculumCourseMembershipFactory(
                    course=new_course,
                    curriculum=self.curriculums[curriculum_id],
                )

    @ddt.data(
        1,  # Scenario 2, within the same Curriculum
        2,  # Scenaario 3, within the same Program
    )
    def test_modify_curriculum_course_membership(self, curriculum_id):
        new_course_run = factories.CourseRunFactory(
            external_key='ext-key-course-1a'
        )
        new_course = new_course_run.course
        curriculum_course_membership = factories.CurriculumCourseMembershipFactory(
            course=new_course,
            curriculum=self.curriculum_3,
        )
        course_run_1a = CourseRun.objects.get(key='course-run-id/course-1a/test')
        message = _duplicate_external_key_message([course_run_1a])
        with self.assertNumQueries(2):
            with self.assertRaisesRegex(ValidationError, escape(message)):  # pylint: disable=deprecated-method
                curriculum_course_membership.curriculum = self.curriculums[curriculum_id]
                curriculum_course_membership.save()

    def test_create_curriculum(self):
        """
        I can't think of any case that would cause the exception on creating a curriculum
        but I will keep this blank test here for enumeration's sake
        """
        pass

    def test_modify_curriculum(self):
        course_run_1a = CourseRun.objects.get(key='course-run-id/course-1a/test')
        _, curriculum_4 = self._create_single_course_curriculum('ext-key-course-1a', 'curriculum_4')
        new_program = factories.ProgramFactory(
            curricula=[curriculum_4]
        )
        message = _duplicate_external_key_message([course_run_1a])
        with self.assertNumQueries(4):
            with self.assertRaisesRegex(ValidationError, escape(message)):  # pylint: disable=deprecated-method
                curriculum_4.program = self.program_1
                curriculum_4.save()
        curriculum_4.refresh_from_db()
        self.assertEqual(curriculum_4.program, new_program)


class ExternalCourseKeyMultipleCollisionTests(ExternalCourseKeyTestDataMixin, TestCase):

    @classmethod
    def setUpTestData(cls):
        """
        Sets up test data for testting multiple collisions of external_keys
        """
        super().setUpTestData()
        cls.course_run_1a = CourseRun.objects.get(key='course-run-id/course-1a/test')
        cls.course_run_2b = CourseRun.objects.get(key='course-run-id/course-2b/test')
        cls.course_run_3c = CourseRun.objects.get(key='course-run-id/course-3c/test')
        cls.course = factories.CourseFactory()
        cls.colliding_course_run_1a = factories.CourseRunFactory(course=cls.course, external_key='ext-key-course-1a')
        cls.colliding_course_run_2b = factories.CourseRunFactory(course=cls.course, external_key='ext-key-course-2b')
        cls.colliding_course_run_3c = factories.CourseRunFactory(course=cls.course, external_key='ext-key-course-3c')
        cls.curriculum = factories.CurriculumFactory()
        cls._add_courses_to_curriculum(cls.curriculum, cls.course)

    def test_multiple_collisions__curriculum_course_membership(self):
        message = _duplicate_external_key_message([self.course_run_1a, self.course_run_2b])
        with self.assertNumQueries(2):
            with self.assertRaisesRegex(ValidationError, escape(message)):  # pylint: disable=deprecated-method
                self._add_courses_to_curriculum(self.curriculum_2, self.course)

    def test_multiple_collisions__curriculum(self):
        message = _duplicate_external_key_message([self.course_run_2b, self.course_run_3c])
        with self.assertNumQueries(4):
            with self.assertRaisesRegex(ValidationError, escape(message)):  # pylint: disable=deprecated-method
                self.curriculum.program = self.program_2
                self.curriculum.save()


class ExternalCourseKeyIncompleteStructureTests(TestCase, ExternalCourseKeyTestMixin):
    """
    Tests that the external_key validation still works within an incomplete hierarchy
    (Course alone or curriculum without a program)
    """

    def test_create_course_run__course_run_only(self):
        course = self._create_course_and_runs()
        course_run = course.course_runs.first()
        message = _duplicate_external_key_message([course_run])
        with self.assertNumQueries(7):
            with self.assertRaisesRegex(ValidationError, escape(message)):  # pylint: disable=deprecated-method
                factories.CourseRunFactory(
                    course=course,
                    external_key=course_run.external_key
                )

    def test_modify_course_run__course_run_only(self):
        course = self._create_course_and_runs(1)
        course_run_1a = course.course_runs.get(external_key='ext-key-course-1a')
        course_run_1b = course.course_runs.get(external_key='ext-key-course-1b')
        message = _duplicate_external_key_message([course_run_1a])
        with self.assertNumQueries(6):
            with self.assertRaisesRegex(ValidationError, escape(message)):  # pylint: disable=deprecated-method
                course_run_1b.external_key = 'ext-key-course-1a'
                course_run_1b.save()

    def test_create_course_run__curriculum_only(self):
        course_run, _ = self._create_single_course_curriculum('colliding-key', 'curriculum_1')
        message = _duplicate_external_key_message([course_run])
        with self.assertNumQueries(7):
            with self.assertRaisesRegex(ValidationError, escape(message)):  # pylint: disable=deprecated-method
                factories.CourseRunFactory(
                    course=course_run.course,
                    external_key='colliding-key'
                )

    def test_modify_course_run__curriculum_only(self):
        course_run_1a, _ = self._create_single_course_curriculum('colliding-key', 'curriculum_1')
        course_run_1b = factories.CourseRunFactory(
            course=course_run_1a.course,
            external_key='this-is-a-different-external-key'
        )
        message = _duplicate_external_key_message([course_run_1a])
        with self.assertNumQueries(6):
            with self.assertRaisesRegex(ValidationError, escape(message)):  # pylint: disable=deprecated-method
                course_run_1b.external_key = 'colliding-key'
                course_run_1b.save()

    def test_create_curriculum_course_membership__curriculum_only(self):
        course_run_1, curriculum_1 = self._create_single_course_curriculum('colliding-key', 'curriculum_1')
        course_run_2 = factories.CourseRunFactory(
            external_key='colliding-key'
        )
        message = _duplicate_external_key_message([course_run_1])
        with self.assertNumQueries(2):
            with self.assertRaisesRegex(ValidationError, escape(message)):  # pylint: disable=deprecated-method
                factories.CurriculumCourseMembershipFactory(
                    course=course_run_2.course,
                    curriculum=curriculum_1,
                )

    def test_modify_curriculum_course_membership__curriculum_only(self):
        course_run_1, curriculum_1 = self._create_single_course_curriculum('colliding-key', 'curriculum_1')
        course_run_2, _ = self._create_single_course_curriculum('colliding-key', 'curriculum_2')
        curriculum_course_membership_2 = course_run_2.course.curriculum_course_membership.first()
        message = _duplicate_external_key_message([course_run_1])
        with self.assertNumQueries(2):
            with self.assertRaisesRegex(ValidationError, escape(message)):  # pylint: disable=deprecated-method
                curriculum_course_membership_2.curriculum = curriculum_1
                curriculum_course_membership_2.save()


class ExternalCourseKeyDBTests(TestCase, ExternalCourseKeyTestMixin):

    def test_mix_of_curriculums_with_and_without_programs(self):
        course_a = self._create_course_and_runs('a')
        course_b = self._create_course_and_runs('b')
        course_c = self._create_course_and_runs('c')
        program_1 = factories.ProgramFactory(title='program_1')
        program_2 = factories.ProgramFactory(title='program_2')
        curriculum_1 = factories.CurriculumFactory(program=program_1)
        curriculum_2 = factories.CurriculumFactory(program=program_2)
        curriculum_3 = factories.CurriculumFactory(program=None)
        curriculum_4 = factories.CurriculumFactory(program=None)
        self._add_courses_to_curriculum(curriculum_1, course_a, course_b)
        self._add_courses_to_curriculum(curriculum_2, course_a, course_b)
        self._add_courses_to_curriculum(curriculum_3, course_a, course_b, course_c)
        self._add_courses_to_curriculum(curriculum_4, course_a, course_b, course_c)

        course_run = course_a.course_runs.first()
        course_run_ca = CourseRun.objects.get(external_key='ext-key-course-ca')
        message = _duplicate_external_key_message([course_run_ca])
        with self.assertNumQueries(FuzzyInt(6, 1)):  # 3 Selects
            with self.assertRaisesRegex(ValidationError, escape(message)):  # pylint: disable=deprecated-method
                course_run.external_key = course_run_ca.external_key
                course_run.save()

        with self.assertNumQueries(FuzzyInt(36, 1)):
            course_run.external_key = 'some-safe-key'
            course_run.save()

    def test_curriculum_repeats(self):
        course_a = self._create_course_and_runs('a')
        course_b = self._create_course_and_runs('b')
        course_c = self._create_course_and_runs('c')
        program = factories.ProgramFactory(title='program_1')
        curriculum_1 = factories.CurriculumFactory(program=program)
        curriculum_2 = factories.CurriculumFactory(program=program)
        curriculum_3 = factories.CurriculumFactory(program=program)
        self._add_courses_to_curriculum(curriculum_1, course_a, course_b, course_c)
        self._add_courses_to_curriculum(curriculum_2, course_a, course_b, course_c)
        self._add_courses_to_curriculum(curriculum_3, course_a, course_b, course_c)
        course_run = course_a.course_runs.first()
        course_run_ba = CourseRun.objects.get(external_key='ext-key-course-ba')
        message = _duplicate_external_key_message([course_run_ba])
        with self.assertNumQueries(FuzzyInt(6, 1)):  # 3 Selects
            with self.assertRaisesRegex(ValidationError, escape(message)):  # pylint: disable=deprecated-method
                course_run.external_key = course_run_ba.external_key
                course_run.save()

        with self.assertNumQueries(FuzzyInt(36, 1)):
            course_run.external_key = 'some-safe-key'
            course_run.save()
