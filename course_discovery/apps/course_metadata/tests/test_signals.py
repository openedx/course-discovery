import datetime
from re import escape

import ddt
import mock
import pytest
from django.apps import apps
from django.core.exceptions import ValidationError
from django.test import TestCase
from factory.django import DjangoModelFactory
from pytz import UTC

from course_discovery.apps.api.v1.tests.test_views.mixins import FuzzyInt
from course_discovery.apps.course_metadata.algolia_models import (
    AlgoliaProxyCourse, AlgoliaProxyProduct, AlgoliaProxyProgram, SearchDefaultResultsConfiguration
)
from course_discovery.apps.course_metadata.choices import CourseRunStatus
from course_discovery.apps.course_metadata.models import (
    BackfillCourseRunSlugsConfig, BackpopulateCourseTypeConfig, BulkModifyProgramHookConfig, CourseRun, Curriculum,
    CurriculumProgramMembership, DataLoaderConfig, DeletePersonDupsConfig, DrupalPublishUuidConfig,
    LevelTypeTranslation, MigratePublisherToCourseMetadataConfig, ProfileImageDownloadConfig, Program,
    ProgramTypeTranslation, RemoveRedirectsConfig, SubjectTranslation, TagCourseUuidsConfig, TopicTranslation
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
        for key, factorylike in factories.__dict__.items():
            if 'NoSignals' in key:
                continue
            if isinstance(factorylike, type) and issubclass(factorylike, DjangoModelFactory):
                if getattr(factorylike, '_meta', None) and factorylike._meta.model:
                    factory_map[factorylike._meta.model] = factorylike

        # These are the models whose post_save and post_delete signals we're
        # connecting to. We want to test each of them.
        for model in apps.get_app_config('course_metadata').get_models():
            # Ignore models that aren't exposed by the API or are only used for testing.
            if model in [BackpopulateCourseTypeConfig, DataLoaderConfig, DeletePersonDupsConfig,
                         DrupalPublishUuidConfig, MigratePublisherToCourseMetadataConfig, SubjectTranslation,
                         TopicTranslation, ProfileImageDownloadConfig, TagCourseUuidsConfig, RemoveRedirectsConfig,
                         BulkModifyProgramHookConfig, BackfillCourseRunSlugsConfig, AlgoliaProxyCourse,
                         AlgoliaProxyProgram, AlgoliaProxyProduct, ProgramTypeTranslation,
                         LevelTypeTranslation, SearchDefaultResultsConfiguration]:
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


@ddt.ddt
class ProgramStructureValidationTests(TestCase):

    @classmethod
    def setUpTestData(cls):
        """
        Set up program structure to test for cycles

        program           p1
                        /    \\
        curriculum     c1      c2
                      /  \\   /  \\
        program      p2    p3     p4
                     |     |
        curriculum   c3    c4
                     | \\  |
        program      p5   p6
        """
        super().setUpTestData()
        cls.program_1 = factories.ProgramFactory(title='program_1')
        cls.program_2 = factories.ProgramFactory(title='program_2')
        cls.program_3 = factories.ProgramFactory(title='program_3')
        cls.program_4 = factories.ProgramFactory(title='program_4')
        cls.program_5 = factories.ProgramFactory(title='program_5')
        cls.program_6 = factories.ProgramFactory(title='program_6')

        cls.curriculum_1 = factories.CurriculumFactory(name='curriculum_1', program=cls.program_1)
        cls.curriculum_2 = factories.CurriculumFactory(name='curriculum_2', program=cls.program_1)
        cls.curriculum_3 = factories.CurriculumFactory(name='curriculum_3', program=cls.program_2)
        cls.curriculum_4 = factories.CurriculumFactory(name='curriculum_4', program=cls.program_3)

        factories.CurriculumProgramMembershipFactory(curriculum=cls.curriculum_1, program=cls.program_2)
        factories.CurriculumProgramMembershipFactory(curriculum=cls.curriculum_1, program=cls.program_3)
        factories.CurriculumProgramMembershipFactory(curriculum=cls.curriculum_2, program=cls.program_3)
        factories.CurriculumProgramMembershipFactory(curriculum=cls.curriculum_2, program=cls.program_4)
        factories.CurriculumProgramMembershipFactory(curriculum=cls.curriculum_3, program=cls.program_5)
        factories.CurriculumProgramMembershipFactory(curriculum=cls.curriculum_3, program=cls.program_6)
        factories.CurriculumProgramMembershipFactory(curriculum=cls.curriculum_4, program=cls.program_6)

    def curriculum_program_membership_error(self, program, curriculum):
        return 'Circular ref error. Program [{}] already contains Curriculum [{}]'.format(
            program,
            curriculum,
        )

    @ddt.data(
        ('program_2', True),    # immediate child program through CurriculumProgramMembership should fail
        ('program_5', True),    # nested child program should fail
        ('program_6', True),    # nested child program with multiple paths to it should fail
        ('program_4', False),   # 'nephew' program is non-circular and should save successfully
        ('program_1', False),   # keeping existing parent program should save successfully
    )
    @ddt.unpack
    def test_update_curriculum_program(self, program_title, is_circular_ref):
        program = Program.objects.get(title=program_title)
        curriculum = self.curriculum_1
        curriculum.program = program

        if is_circular_ref:
            expected_error = 'Circular ref error.  Curriculum already contains program {}'.format(program)
            with self.assertRaisesRegex(ValidationError, escape(expected_error)):
                curriculum.save()
        else:
            curriculum.save()
            curriculum.refresh_from_db()
            self.assertEqual(curriculum.program.title, program_title)

    def test_create_new_curriculum(self):
        """ create should be unaffected, impossible to create circular ref """
        factories.CurriculumFactory(program=self.program_2)

    @ddt.data(
        ('curriculum_1', 'program_1', True),    # parent program as member program should fail
        ('curriculum_3', 'program_1', True),    # nth parent program up tree as member program should fail
        ('curriculum_4', 'program_1', True),    # nth parent program with multiple search paths as member should fail
        ('curriculum_4', 'program_2', False),   # valid non-circular CurriculumProgramMembership
    )
    @ddt.unpack
    def test_create_curriculum_program_membership(self, curriculum_name, program_title, is_circular_ref):
        curriculum = Curriculum.objects.get(name=curriculum_name)
        program = Program.objects.get(title=program_title)

        if is_circular_ref:
            expected_error = self.curriculum_program_membership_error(program, curriculum)
            with self.assertRaisesRegex(ValidationError, escape(expected_error)):
                CurriculumProgramMembership.objects.create(
                    program=program,
                    curriculum=curriculum,
                )
        else:
            CurriculumProgramMembership.objects.create(
                program=program,
                curriculum=curriculum,
            )

    @ddt.data(
        ('program_5', False),   # update to valid program
        ('program_1', True),    # update creates circular reference
        ('program_6', False),   # re-saving with existing model should succeed
    )
    @ddt.unpack
    def test_update_curriculum_program_membership(self, new_program_title, is_circular_ref):
        membership = CurriculumProgramMembership.objects.get(curriculum=self.curriculum_4, program=self.program_6)
        new_program = Program.objects.get(title=new_program_title)
        membership.program = new_program

        if is_circular_ref:
            expected_error = self.curriculum_program_membership_error(new_program, self.curriculum_4)
            with self.assertRaisesRegex(ValidationError, escape(expected_error)):
                membership.save()
        else:
            membership.save()


class ExternalCourseKeyTestMixin:

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
                end=datetime.datetime(2014, 1, 1, tzinfo=UTC),
                enrollment_end=datetime.datetime(2014, 1, 1, tzinfo=UTC),
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
        with self.assertNumQueries(12, threshold=0):
            with self.assertRaisesRegex(ValidationError, escape(message)):
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
            with self.assertRaisesRegex(ValidationError, escape(message)):
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
            with self.assertRaisesRegex(ValidationError, escape(message)):
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
            with self.assertRaisesRegex(ValidationError, escape(message)):
                curriculum_course_membership.curriculum = self.curriculums[curriculum_id]
                curriculum_course_membership.save()

    def test_create_curriculum(self):
        """
        I can't think of any case that would cause the exception on creating a curriculum
        but I will keep this blank test here for enumeration's sake
        """

    def test_modify_curriculum(self):
        course_run_1a = CourseRun.objects.get(key='course-run-id/course-1a/test')
        _, curriculum_4 = self._create_single_course_curriculum('ext-key-course-1a', 'curriculum_4')
        new_program = factories.ProgramFactory(
            curricula=[curriculum_4]
        )
        message = _duplicate_external_key_message([course_run_1a])
        with self.assertNumQueries(5):
            with self.assertRaisesRegex(ValidationError, escape(message)):
                curriculum_4.program = self.program_1
                curriculum_4.save()
        curriculum_4.refresh_from_db()
        self.assertEqual(curriculum_4.program, new_program)

    @ddt.data(
        None,
        '',
    )
    def test_external_course_key_null_or_empty(self, external_key_to_test):
        course_run_1a = CourseRun.objects.get(key='course-run-id/course-1a/test')
        course_run_1a.external_key = external_key_to_test
        course_run_1a.save()

        # Same course test
        copy_course_run_1a = factories.CourseRunFactory(
            course=self.course_1,
            external_key=external_key_to_test,
        )
        self.assertEqual(course_run_1a.external_key, copy_course_run_1a.external_key)

        # Same curriculum test but different courses
        new_course_run = factories.CourseRunFactory(
            external_key=external_key_to_test
        )
        new_course = new_course_run.course
        factories.CurriculumCourseMembershipFactory(
            course=new_course,
            curriculum=self.curriculum_1,
        )
        self.assertEqual(course_run_1a.external_key, new_course_run.external_key)

        # Same programs but different curriculum test
        _, curriculum_4 = self._create_single_course_curriculum(external_key_to_test, 'curriculum_4')
        curriculum_4.program = self.program_1
        curriculum_4.save()
        curriculum_4.refresh_from_db()


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
            with self.assertRaisesRegex(ValidationError, escape(message)):
                self._add_courses_to_curriculum(self.curriculum_2, self.course)

    def test_multiple_collisions__curriculum(self):
        message = _duplicate_external_key_message([self.course_run_2b, self.course_run_3c])
        with self.assertNumQueries(5):
            with self.assertRaisesRegex(ValidationError, escape(message)):
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
        with self.assertNumQueries(11, threshold=0):
            with self.assertRaisesRegex(ValidationError, escape(message)):
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
            with self.assertRaisesRegex(ValidationError, escape(message)):
                course_run_1b.external_key = 'ext-key-course-1a'
                course_run_1b.save()

    def test_create_course_run__curriculum_only(self):
        course_run, _ = self._create_single_course_curriculum('colliding-key', 'curriculum_1')
        message = _duplicate_external_key_message([course_run])
        with self.assertNumQueries(11, threshold=0):
            with self.assertRaisesRegex(ValidationError, escape(message)):
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
            with self.assertRaisesRegex(ValidationError, escape(message)):
                course_run_1b.external_key = 'colliding-key'
                course_run_1b.save()

    def test_create_curriculum_course_membership__curriculum_only(self):
        course_run_1, curriculum_1 = self._create_single_course_curriculum('colliding-key', 'curriculum_1')
        course_run_2 = factories.CourseRunFactory(
            external_key='colliding-key'
        )
        message = _duplicate_external_key_message([course_run_1])
        with self.assertNumQueries(2):
            with self.assertRaisesRegex(ValidationError, escape(message)):
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
            with self.assertRaisesRegex(ValidationError, escape(message)):
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
            with self.assertRaisesRegex(ValidationError, escape(message)):
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
            with self.assertRaisesRegex(ValidationError, escape(message)):
                course_run.external_key = course_run_ba.external_key
                course_run.save()

        with self.assertNumQueries(FuzzyInt(36, 1)):
            course_run.external_key = 'some-safe-key'
            course_run.save()


class ExternalCourseKeyDraftTests(ExternalCourseKeyTestDataMixin, TestCase):
    """
    Tests for the behavior of draft Course Runs.
    Draft or not, a course run will only be checked for collisions against _published_ courseruns.
    """

    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        cls.draft_course_1 = factories.CourseFactory(
            draft=True,
            key='course-id/draft-course-1/test',
            title='draft-course-1'
        )
        cls.draft_course_run_1 = factories.CourseRunFactory(
            course=cls.draft_course_1,
            draft=True,
            external_key='external-key-drafttest'
        )

    def test_draft_does_not_collide_with_draft(self):
        with self.assertNumQueries(77, threshold=0):
            factories.CourseRunFactory(
                course=self.course_1,
                draft=True,
                external_key='external-key-drafttest',
                end=datetime.datetime(2014, 1, 1, tzinfo=UTC),
                enrollment_end=datetime.datetime(2014, 1, 1, tzinfo=UTC),
            )

    def test_draft_collides_with_nondraft(self):
        course_run_1a = self.course_1.course_runs.get(external_key='ext-key-course-1a')
        message = _duplicate_external_key_message([course_run_1a])
        with self.assertNumQueries(12, threshold=0):
            with self.assertRaisesRegex(ValidationError, escape(message)):
                factories.CourseRunFactory(
                    course=self.course_1,
                    draft=True,
                    external_key='ext-key-course-1a',
                )

    def test_nondraft_does_not_collide_with_draft(self):
        with self.assertNumQueries(77, threshold=0):
            factories.CourseRunFactory(
                course=self.course_1,
                draft=False,
                external_key='external-key-drafttest',
                end=datetime.datetime(2014, 1, 1, tzinfo=UTC),
                enrollment_end=datetime.datetime(2014, 1, 1, tzinfo=UTC),
            )

    def test_collision_does_not_include_drafts(self):
        with self.assertNumQueries(77, threshold=0):
            course_run = factories.CourseRunFactory(
                course=self.course_1,
                draft=False,
                external_key='external-key-drafttest',
                end=datetime.datetime(2014, 1, 1, tzinfo=UTC),
                enrollment_end=datetime.datetime(2014, 1, 1, tzinfo=UTC),
            )
        message = _duplicate_external_key_message([course_run])  # Not draft_course_run_1
        with self.assertNumQueries(11, threshold=0):
            with self.assertRaisesRegex(ValidationError, escape(message)):
                factories.CourseRunFactory(
                    course=self.course_1,
                    draft=False,
                    external_key='external-key-drafttest',
                    end=datetime.datetime(2014, 1, 1, tzinfo=UTC),
                    enrollment_end=datetime.datetime(2014, 1, 1, tzinfo=UTC),
                )

    def test_update_or_create_official_version(self):
        # This test implicitly checks that a collision does not happen
        # and that the external_key is properly copied over to the official version
        self.draft_course_run_1.update_or_create_official_version()
        official_run = self.draft_course_run_1.official_version
        self.assertEqual(self.draft_course_run_1.external_key, official_run.external_key)


class SalesforceTests(TestCase):
    def setUp(self):
        super().setUp()
        self.salesforce_util_path = 'course_discovery.apps.course_metadata.utils.SalesforceUtil'

    def test_update_or_create_salesforce_organization(self):
        with mock.patch(self.salesforce_util_path) as mock_salesforce_util:
            organization = factories.OrganizationFactory()

            mock_salesforce_util().create_publisher_organization.assert_called()
            mock_salesforce_util().update_publisher_organization.assert_not_called()

            organization.name = 'changed'
            organization.save()

            mock_salesforce_util().update_publisher_organization.assert_called()

    def test_update_or_create_salesforce_course(self):
        with mock.patch(self.salesforce_util_path) as mock_salesforce_util:
            # Does not update for non-drafts
            course = factories.CourseFactory(draft=True)

            mock_salesforce_util().create_course.assert_not_called()
            mock_salesforce_util().update_course.assert_not_called()

            course.save()

            # This shows that an update to a draft does not hit the salesforce update method
            mock_salesforce_util().update_course.assert_not_called()
            organization = factories.OrganizationFactory()
            course.authoring_organizations.add(organization)

            course.draft = False
            course.title = 'changed'
            course.save()

            self.assertEqual(1, mock_salesforce_util().update_course.call_count)

    def test_update_or_create_salesforce_course_run(self):
        with mock.patch(self.salesforce_util_path) as mock_salesforce_util:
            course_run = factories.CourseRunFactory(draft=True, status=CourseRunStatus.Published)

            mock_salesforce_util().create_course_run.assert_called()
            mock_salesforce_util().update_course_run.assert_not_called()

            course_run.draft = False
            course_run.status = CourseRunStatus.Unpublished
            course_run.save()

            mock_salesforce_util().update_course_run.assert_called()

    def test_authoring_organizations_changed(self):
        with mock.patch(self.salesforce_util_path) as mock_salesforce_util:
            # Does not update for non-draftstest_comments.py
            organization = factories.OrganizationFactory()
            course = factories.CourseFactory(draft=False)

            course.authoring_organizations.add(organization)
            mock_salesforce_util().create_course.assert_not_called()

            # Updates for drafts when an auth org is added (new) courses
            organization = factories.OrganizationFactory()

            course = factories.CourseFactory(draft=True)

            course.authoring_organizations.add(organization)
            mock_salesforce_util().create_course.assert_called()
