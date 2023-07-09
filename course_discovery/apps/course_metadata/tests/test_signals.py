
import datetime
from re import escape
from unittest import mock

import ddt
import pytest
from django.apps import apps
from django.conf import settings
from django.core.exceptions import ValidationError
from django.db.models.signals import m2m_changed
from django.test import TestCase, override_settings
from factory.django import DjangoModelFactory
from opaque_keys.edx.keys import CourseKey
from openedx_events.content_authoring.data import CourseCatalogData, CourseScheduleData
from openedx_events.event_bus import EventsMetadata
from pytz import UTC
from testfixtures import LogCapture

from course_discovery.apps.api.v1.tests.test_views.mixins import FuzzyInt
from course_discovery.apps.core.tests.factories import PartnerFactory, UserFactory
from course_discovery.apps.course_metadata.algolia_models import (
    AlgoliaProxyCourse, AlgoliaProxyProduct, AlgoliaProxyProgram, SearchDefaultResultsConfiguration
)
from course_discovery.apps.course_metadata.choices import CourseRunStatus
from course_discovery.apps.course_metadata.models import (
    AdditionalMetadata, BackfillCourseRunSlugsConfig, BackpopulateCourseTypeConfig, BulkModifyProgramHookConfig,
    BulkUpdateImagesConfig, BulkUploadTagsConfig, Course, CourseEditor, CourseRun, CSVDataLoaderConfiguration,
    Curriculum, CurriculumProgramMembership, DataLoaderConfig, DeduplicateHistoryConfig, DeletePersonDupsConfig,
    DrupalPublishUuidConfig, LevelTypeTranslation, MigrateCourseSlugConfiguration,
    MigratePublisherToCourseMetadataConfig, ProductMeta, ProfileImageDownloadConfig, Program, ProgramTypeTranslation,
    RemoveRedirectsConfig, SubjectTranslation, TagCourseUuidsConfig, TopicTranslation
)
from course_discovery.apps.course_metadata.signals import (
    _duplicate_external_key_message, additional_metadata_facts_changed,
    connect_course_data_modified_timestamp_signal_handlers, course_collaborators_changed, course_run_staff_changed,
    course_run_transcript_languages_changed, course_subjects_changed, course_topics_taggable_changed,
    disconnect_course_data_modified_timestamp_signal_handlers, product_meta_taggable_changed,
    update_course_data_from_event
)
from course_discovery.apps.course_metadata.tests import factories
from course_discovery.apps.course_metadata.tests.factories import CourseEditorFactory, CourseFactory
from course_discovery.apps.ietf_language_tags.models import LanguageTag
from course_discovery.apps.publisher.tests.factories import GroupFactory, OrganizationExtensionFactory

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
                         LevelTypeTranslation, SearchDefaultResultsConfiguration, BulkUpdateImagesConfig,
                         BulkUploadTagsConfig, CSVDataLoaderConfiguration, DeduplicateHistoryConfig,
                         MigrateCourseSlugConfiguration]:
                continue
            if 'abstract' in model.__name__.lower() or 'historical' in model.__name__.lower():
                continue

            factory = factory_map.get(model)
            if not factory:
                pytest.fail(f'The {model} model is missing a factory.')

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
            expected_error = f'Circular ref error.  Curriculum already contains program {program}'
            with self.assertRaisesRegex(ValidationError, escape(expected_error)):
                curriculum.save()
        else:
            curriculum.save()
            curriculum.refresh_from_db()
            assert curriculum.program.title == program_title

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
        course_name = f'course-{course_identifier}'
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
    def setUpClass(cls):
        """
        Sets up the tree for testing external course keys

        program          1         2
                        / \\       |
        curriculum    1    2      3
                      |     \\   / \\
        course        1        2     3
        """
        super().setUpClass()
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
        with self.assertNumQueries(12):
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
        assert curriculum_4.program == new_program

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
        assert course_run_1a.external_key == copy_course_run_1a.external_key

        # Same curriculum test but different courses
        new_course_run = factories.CourseRunFactory(
            external_key=external_key_to_test
        )
        new_course = new_course_run.course
        factories.CurriculumCourseMembershipFactory(
            course=new_course,
            curriculum=self.curriculum_1,
        )
        assert course_run_1a.external_key == new_course_run.external_key

        # Same programs but different curriculum test
        _, curriculum_4 = self._create_single_course_curriculum(external_key_to_test, 'curriculum_4')
        curriculum_4.program = self.program_1
        curriculum_4.save()
        curriculum_4.refresh_from_db()


class ExternalCourseKeyMultipleCollisionTests(ExternalCourseKeyTestDataMixin, TestCase):

    @classmethod
    def setUpClass(cls):
        """
        Sets up test data for testting multiple collisions of external_keys
        """
        super().setUpClass()
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
        course.partner.marketing_site_url_root = ''
        course.partner.save()
        course_run = course.course_runs.first()
        message = _duplicate_external_key_message([course_run])
        with self.assertNumQueries(11):
            with self.assertRaisesRegex(ValidationError, escape(message)):
                factories.CourseRunFactory(
                    course=course,
                    external_key=course_run.external_key
                )

    def test_modify_course_run__course_run_only(self):
        course = self._create_course_and_runs(1)
        course.partner.marketing_site_url_root = ''
        course.partner.save()
        course_run_1a = course.course_runs.get(external_key='ext-key-course-1a')
        course_run_1b = course.course_runs.get(external_key='ext-key-course-1b')
        message = _duplicate_external_key_message([course_run_1a])
        with self.assertNumQueries(6):
            with self.assertRaisesRegex(ValidationError, escape(message)):
                course_run_1b.external_key = 'ext-key-course-1a'
                course_run_1b.save()

    def test_create_course_run__curriculum_only(self):
        course_run, _ = self._create_single_course_curriculum('colliding-key', 'curriculum_1')
        course = course_run.course
        course.partner.marketing_site_url_root = ''
        course.partner.save()
        message = _duplicate_external_key_message([course_run])
        with self.assertNumQueries(11):
            with self.assertRaisesRegex(ValidationError, escape(message)):
                factories.CourseRunFactory(
                    course=course,
                    external_key='colliding-key'
                )

    def test_modify_course_run__curriculum_only(self):
        course_run_1a, _ = self._create_single_course_curriculum('colliding-key', 'curriculum_1')
        course_run_1b = factories.CourseRunFactory(
            course=course_run_1a.course,
            external_key='this-is-a-different-external-key'
        )
        course = course_run_1b.course
        course.partner.marketing_site_url_root = ''
        course.partner.save()
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

        with self.assertNumQueries(FuzzyInt(65, 10)):
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

        with self.assertNumQueries(FuzzyInt(65, 10)):
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
        with self.assertNumQueries(FuzzyInt(28, 10)):
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
        with self.assertNumQueries(12):
            with self.assertRaisesRegex(ValidationError, escape(message)):
                factories.CourseRunFactory(
                    course=self.course_1,
                    draft=True,
                    external_key='ext-key-course-1a',
                )

    def test_nondraft_does_not_collide_with_draft(self):
        with self.assertNumQueries(FuzzyInt(133, 10)):
            factories.CourseRunFactory(
                course=self.course_1,
                draft=False,
                external_key='external-key-drafttest',
                end=datetime.datetime(2014, 1, 1, tzinfo=UTC),
                enrollment_end=datetime.datetime(2014, 1, 1, tzinfo=UTC),
            )

    def test_collision_does_not_include_drafts(self):
        with self.assertNumQueries(FuzzyInt(132, 10)):
            course_run = factories.CourseRunFactory(
                course=self.course_1,
                draft=False,
                external_key='external-key-drafttest',
                end=datetime.datetime(2014, 1, 1, tzinfo=UTC),
                enrollment_end=datetime.datetime(2014, 1, 1, tzinfo=UTC),
            )
        message = _duplicate_external_key_message([course_run])  # Not draft_course_run_1
        with self.assertNumQueries(FuzzyInt(11, 5)):
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
        assert self.draft_course_run_1.external_key == official_run.external_key


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

            assert 1 == mock_salesforce_util().update_course.call_count

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


class TestCourseDataUpdateSignal(TestCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        factories.SourceFactory(slug=settings.DEFAULT_PRODUCT_SOURCE_SLUG)

    def setUp(self):
        self.course_key = CourseKey.from_string('course-v1:SC+BreadX+3T2015')
        self.scheduling_data = CourseScheduleData(
            start=datetime.datetime(2014, 1, 1, tzinfo=UTC),
            end=datetime.datetime(2014, 1, 1, tzinfo=UTC),
            enrollment_start=datetime.datetime(2014, 1, 1, tzinfo=UTC),
            enrollment_end=datetime.datetime(2014, 1, 1, tzinfo=UTC),
            pacing='self',
        )
        self.catalog_data = CourseCatalogData(
            course_key=self.course_key,
            name='Test Course',
            schedule_data=self.scheduling_data,
            hidden=False,
        )
        self.partner = PartnerFactory(id=settings.DEFAULT_PARTNER_ID)

    def test_event_creates_new_course(self):
        update_course_data_from_event(catalog_info=self.catalog_data)
        course_run = CourseRun.objects.get(key=self.course_key)

        assert course_run.title == self.catalog_data.name
        assert course_run.hidden == self.catalog_data.hidden
        assert course_run.start == self.catalog_data.schedule_data.start
        assert course_run.end == self.catalog_data.schedule_data.end
        assert course_run.enrollment_start == self.catalog_data.schedule_data.enrollment_start
        assert course_run.enrollment_end == self.catalog_data.schedule_data.enrollment_end
        # What the api expects and what the data is saved as are slightly different.
        assert course_run.pacing_type == 'self_paced'

        course = course_run.course
        assert course.title == self.catalog_data.name

    def test_event_idempotent(self):
        update_course_data_from_event(catalog_info=self.catalog_data)
        course_run = CourseRun.objects.get(key=self.course_key)
        assert course_run.title == self.catalog_data.name
        assert course_run.hidden == self.catalog_data.hidden
        assert course_run.start == self.catalog_data.schedule_data.start
        assert course_run.end == self.catalog_data.schedule_data.end
        assert course_run.enrollment_start == self.catalog_data.schedule_data.enrollment_start
        assert course_run.enrollment_end == self.catalog_data.schedule_data.enrollment_end
        # What the api expects and what the data is saved as are slightly different.
        assert course_run.pacing_type == 'self_paced'

        # Run twice.
        update_course_data_from_event(catalog_info=self.catalog_data)
        course_run = CourseRun.objects.get(key=self.course_key)
        assert course_run.title == self.catalog_data.name
        assert course_run.hidden == self.catalog_data.hidden
        assert course_run.start == self.catalog_data.schedule_data.start
        assert course_run.end == self.catalog_data.schedule_data.end
        assert course_run.enrollment_start == self.catalog_data.schedule_data.enrollment_start
        assert course_run.enrollment_end == self.catalog_data.schedule_data.enrollment_end
        # What the api expects and what the data is saved as are slightly different.
        assert course_run.pacing_type == 'self_paced'

    def test_optional_data(self):
        scheduling_data = CourseScheduleData(
            start=datetime.datetime(2014, 1, 1, tzinfo=UTC),
            pacing='self',
        )
        catalog_data = CourseCatalogData(
            course_key=self.course_key,
            name='Test Course',
            schedule_data=scheduling_data,
        )
        update_course_data_from_event(catalog_info=catalog_data)
        course_run = CourseRun.objects.get(key=self.course_key)

        assert course_run.title == self.catalog_data.name
        assert course_run.start == self.catalog_data.schedule_data.start
        assert course_run.pacing_type == 'self_paced'

    def test_update_existing_course(self):
        factories.CourseRunFactory(key=str(self.course_key))
        course_run = CourseRun.objects.get(key=self.course_key)

        assert course_run.title != self.catalog_data.name
        assert course_run.start != self.catalog_data.schedule_data.start

        update_course_data_from_event(catalog_info=self.catalog_data)
        course_run = CourseRun.objects.get(key=self.course_key)

        assert course_run.title == self.catalog_data.name
        assert course_run.start == self.catalog_data.schedule_data.start

    def test_clear_existing_course_option_data(self):
        # Check that missing fields in the signal will
        # clear the field in the course.
        factories.CourseRunFactory(key=str(self.course_key))
        course_run = CourseRun.objects.get(key=self.course_key)

        scheduling_data = CourseScheduleData(
            start=datetime.datetime(2014, 1, 1, tzinfo=UTC),
            pacing='self',
        )
        catalog_data = CourseCatalogData(
            course_key=self.course_key,
            name='Test Course',
            schedule_data=scheduling_data,
        )

        assert course_run.title != catalog_data.name
        assert course_run.start != catalog_data.schedule_data.start
        assert course_run.end is not None
        assert course_run.enrollment_end is not None
        assert course_run.enrollment_start is not None

        update_course_data_from_event(catalog_info=catalog_data)
        course_run = CourseRun.objects.get(key=self.course_key)

        assert course_run.title == self.catalog_data.name
        assert course_run.start == self.catalog_data.schedule_data.start
        assert course_run.end is None
        assert course_run.enrollment_end is None
        assert course_run.enrollment_start is None

    def test_error_cases(self):
        with self.assertLogs() as captured_logs:
            update_course_data_from_event(catalog_info=None)
            assert 'Received null or incorrect data from COURSE_CATALOG_INFO_CHANGED.' in captured_logs.output[0]

        catalog_data = CourseCatalogData(
            course_key='invalid course key',
            name='a name',
            schedule_data=self.scheduling_data,
        )
        with self.assertLogs('course_discovery.apps.course_metadata.data_loaders.api') as captured_logs:
            update_course_data_from_event(catalog_info=catalog_data)
            assert 'An error occurred while updating' in captured_logs.output[1]

    @mock.patch('time.sleep')
    def test_event_processing_delay(self, sleep_patch):
        """
        Verify that event processing is artificially delayed if the event is received within delay
        applicable time window.
        """
        metadata = EventsMetadata(event_type='catalog-data-changed', minorversion=0)
        with override_settings(EVENT_BUS_MESSAGE_DELAY_THRESHOLD_SECONDS=120):
            with self.assertLogs(LOGGER_NAME, level="DEBUG") as logger:
                update_course_data_from_event(
                    catalog_info=self.catalog_data,
                    metadata=metadata
                )
                assert f"COURSE_CATALOG_INFO_CHANGED event received within the " \
                       f"delay applicable window for course run {self.course_key}." in logger.output[0]

        sleep_patch.assert_called_once_with(settings.EVENT_BUS_PROCESSING_DELAY_SECONDS)


class OrganizationGroupRemovalTests(TestCase):
    """
    Tests for the handle_organization_group_removal signal handler
    """
    def setUp(self):
        self.user_1 = UserFactory(username="user1")
        self.user_2 = UserFactory(username="user2")
        self.user_3 = UserFactory(username="user3")

        self.group_1 = GroupFactory()

        self.org_ext_1 = OrganizationExtensionFactory()
        self.org_ext_2 = OrganizationExtensionFactory()
        self.org_ext_3 = OrganizationExtensionFactory()

        self.course_1 = CourseFactory(authoring_organizations=[self.org_ext_1.organization])
        self.course_2 = CourseFactory(
            authoring_organizations=[self.org_ext_1.organization, self.org_ext_2.organization]
        )
        self.course_3 = CourseFactory(authoring_organizations=[self.org_ext_3.organization])

        self.user_1_course_editor_1 = CourseEditorFactory(user=self.user_1, course=self.course_1)
        self.user_2_course_editor_1 = CourseEditorFactory(user=self.user_2, course=self.course_1)
        self.user_2_course_editor_2 = CourseEditorFactory(user=self.user_2, course=self.course_2)
        self.user_3_course_editor_1 = CourseEditorFactory(user=self.user_3, course=self.course_1)
        self.user_3_course_editor_2 = CourseEditorFactory(user=self.user_3, course=self.course_3)

    def test_single_authoring_org(self):
        """
        Test that course editor is removed for course with single authoring organization
        """
        with self.assertLogs(LOGGER_NAME, level="INFO") as captured_logs:
            assert CourseEditor.objects.count() == 5
            self.user_1.groups.add(self.group_1, self.org_ext_1.group)
            self.user_1.groups.remove(self.org_ext_1.group)
            assert CourseEditor.objects.filter(user=self.user_1).count() == 0
            assert CourseEditor.objects.count() == 4
            assert (
                f'User {self.user_1.username} no longer holds editor privileges for course {self.course_1.title}'
                in captured_logs.output[0]
            )

    def test_multiple_authoring_orgs(self):
        """
        Test that course editor is not removed for course with multiple authoring
        orgs if the user is in both orgs and only removed from once
        """
        assert CourseEditor.objects.count() == 5
        self.user_2.groups.add(self.org_ext_1.group, self.org_ext_2.group)
        self.user_2.groups.remove(self.org_ext_2.group)
        assert CourseEditor.objects.filter(user=self.user_2).count() == 2
        assert CourseEditor.objects.count() == 5

    def test_no_org(self):
        """
        Verify that removal of a group that is not linked to any org
        has no effect
        """
        assert CourseEditor.objects.count() == 5
        self.user_1.groups.add(self.group_1, self.org_ext_1.group)
        self.user_1.groups.remove(self.group_1)
        assert CourseEditor.objects.filter(user=self.user_1).count() == 1
        assert CourseEditor.objects.count() == 5

    def test_remove_multiple_groups(self):
        """
        Test that removing multiple groups at once works as expected
        """
        with self.assertLogs(LOGGER_NAME) as captured_logs:
            assert CourseEditor.objects.count() == 5
            self.user_3.groups.add(self.org_ext_1.group, self.org_ext_3.group)
            self.user_3.groups.remove(self.org_ext_1.group, self.org_ext_3.group)
            assert CourseEditor.objects.filter(user=self.user_3).count() == 0
            assert CourseEditor.objects.count() == 3
            assert (
                f'User {self.user_3.username} no longer holds editor privileges for course {self.course_1.title}'
                in captured_logs.output[0]
            )
            assert (
                f'User {self.user_3.username} no longer holds editor privileges for course {self.course_3.title}'
                in captured_logs.output[1]
            )

    def test_remove_orphan_editors(self):
        """
        Test that removing a group for a user deletes the user's orphan editor instances too.

        Orphan editor instances are CourseEditor instances where the user is not a member of the course's organizations.
        """
        with self.assertLogs(LOGGER_NAME) as captured_logs:
            assert CourseEditor.objects.count() == 5
            self.user_3.groups.add(self.org_ext_3.group)
            self.user_3.groups.remove(self.org_ext_3.group)
            assert CourseEditor.objects.filter(user=self.user_3).count() == 0
            assert CourseEditor.objects.count() == 3
            assert (
                f'User {self.user_3.username} no longer holds editor privileges for course {self.course_1.title}'
                in captured_logs.output[0]
            )
            assert (
                f'User {self.user_3.username} no longer holds editor privileges for course {self.course_3.title}'
                in captured_logs.output[1]
            )

    def test_no_reverse_update_trigger(self):
        """
        Test that updating the relation from Group to User does not
        affect any CourseEditor instances
        """
        assert CourseEditor.objects.count() == 5
        self.user_1.groups.add(self.group_1, self.org_ext_1.group)
        self.group_1.user_set.remove(self.user_1)
        self.org_ext_1.group.user_set.remove(self.user_1)
        assert self.user_1.groups.count() == 0
        assert CourseEditor.objects.filter(user=self.user_1).count() == 1
        assert CourseEditor.objects.count() == 5


class DataModifiedTimestampUpdateSignalsTests(TestCase):
    """
    This test suite is meant for testing various signal handlers that update data modified timestamps on
    Course & Program.

      * additional_metadata_facts_changed
      * course_run_staff_changed
      * course_run_transcript_languages_changed
      * course_collaborators_changed
      * course_subjects_changed
      * product_meta_taggable_changed
      * course_topics_taggable_changed
    """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        disconnect_course_data_modified_timestamp_signal_handlers()

    @classmethod
    def tearDownClass(cls) -> None:
        connect_course_data_modified_timestamp_signal_handlers()
        super().tearDownClass()

    def test_product_meta_keywords_change(self):
        """
        Verify that updating the keywords on ProductMeta triggers the update_data_modified_timestamp
        for ProductMeta and updates data_modified_timestamp for related courses.
        """
        m2m_changed.connect(product_meta_taggable_changed, sender=ProductMeta.keywords.through)
        product_meta = factories.ProductMetaFactory()
        course = factories.CourseFactory(
            draft=True,
            additional_metadata=factories.AdditionalMetadataFactory(
                product_meta=product_meta
            )
        )
        course_timestamp = course.data_modified_timestamp

        with LogCapture(LOGGER_NAME) as log:
            product_meta.keywords.set(['keyword_1', 'keyword_2'])

        course.refresh_from_db()
        assert course_timestamp < course.data_modified_timestamp

        log.check_present(
            (
                LOGGER_NAME,
                'INFO',
                f"{product_meta.keywords.through} has been updated for ProductMeta {product_meta.pk}."
            )
        )
        m2m_changed.disconnect(product_meta_taggable_changed, sender=ProductMeta.keywords.through)

    def test_course_topics_taggable_change(self):
        """
        Verify that updating the keywords on ProductMeta triggers the update_data_modified_timestamp
        for ProductMeta and updates data_modified_timestamp for related courses.
        """
        m2m_changed.connect(course_topics_taggable_changed, sender=Course.topics.through)
        course = factories.CourseFactory(draft=True)
        course_timestamp = course.data_modified_timestamp

        with LogCapture(LOGGER_NAME) as log:
            course.topics.set(['keyword_1', 'keyword_2'])

        course.refresh_from_db()
        assert course_timestamp < course.data_modified_timestamp

        log.check_present(
            (
                LOGGER_NAME,
                'INFO',
                f"{course.topics.through} has been updated for Course {course.key}."
            )
        )
        # Attempting to set the same keywords does not update the timestamp
        course_timestamp = course.data_modified_timestamp
        course.topics.set(['keyword_1', 'keyword_2'])
        course.refresh_from_db()
        assert course_timestamp == course.data_modified_timestamp
        m2m_changed.connect(course_topics_taggable_changed, sender=Course.topics.through)

    def test_additional_metadata_fact_addition(self):
        """
        Verify that adding Fact objects on AdditionalMetadata triggers the update_data_modified_timestamp
        for AdditionalMetadata and updates data_modified_timestamp for related courses.
        """
        m2m_changed.connect(additional_metadata_facts_changed, sender=AdditionalMetadata.facts.through)
        additional_metadata = factories.AdditionalMetadataFactory()
        course = factories.CourseFactory(
            draft=True,
            additional_metadata=additional_metadata
        )
        fact_1 = factories.FactFactory()
        fact_2 = factories.FactFactory()
        course_timestamp = course.data_modified_timestamp
        with LogCapture(LOGGER_NAME) as log:
            additional_metadata.facts.add(fact_1, fact_2)
        course.refresh_from_db()
        assert course_timestamp < course.data_modified_timestamp
        log.check_present(
            (
                LOGGER_NAME,
                'INFO',
                f"{additional_metadata.facts.through} has been updated for "
                f"AdditionalMetadata {additional_metadata.pk}."
            )
        )
        m2m_changed.disconnect(additional_metadata_facts_changed, sender=AdditionalMetadata.facts.through)

    def test_course_collaborators_change__non_draft_present(self):
        """
        Verify the change in course collaborators will update the data timestamp for Course if the non-draft version
        of the course is present.
        """
        m2m_changed.connect(course_collaborators_changed, sender=Course.collaborators.through)

        draft_course = CourseFactory(draft=True)
        non_draft_course = CourseFactory(draft_version=draft_course, key=draft_course.key)
        course_timestamp = draft_course.data_modified_timestamp
        collaborator_1 = factories.CollaboratorFactory()
        collaborator_2 = factories.CollaboratorFactory()
        collaborator_3 = factories.CollaboratorFactory()
        non_draft_course.collaborators.add(collaborator_1, collaborator_2, collaborator_3)

        with LogCapture(LOGGER_NAME) as log:
            draft_course.collaborators.set((collaborator_1, collaborator_2))
        draft_course.refresh_from_db()
        assert course_timestamp < draft_course.data_modified_timestamp
        log.check_present(
            (
                LOGGER_NAME,
                'INFO',
                f"Collaborator M2M relation has been updated for course {draft_course.key}."
            )
        )
        m2m_changed.disconnect(course_collaborators_changed, sender=Course.collaborators.through)

    def test_course_collaborators_change__non_draft_missing(self):
        """
        Verify the change in course collaborators will not update the data timestamp for Course if course does not
        have a non-draft version.
        """
        m2m_changed.connect(course_collaborators_changed, sender=Course.collaborators.through)

        course = CourseFactory(draft=True)
        course_timestamp = course.data_modified_timestamp
        collaborator_1 = factories.CollaboratorFactory()
        collaborator_2 = factories.CollaboratorFactory()

        with LogCapture(LOGGER_NAME) as log:
            course.collaborators.set((collaborator_1, collaborator_2))
        course.refresh_from_db()
        assert course_timestamp == course.data_modified_timestamp
        with self.assertRaises(AssertionError):
            log.check_present(
                (
                    LOGGER_NAME,
                    'INFO',
                    f"Collaborator M2M relation has been updated for course {course.key}."
                )
            )

        m2m_changed.disconnect(course_collaborators_changed, sender=Course.collaborators.through)

    def test_course_subjects_change__non_draft_present(self):
        """
        Verify the change in course subjects will update the data timestamp for Course if the non-draft version
        of the course is present.
        """
        m2m_changed.connect(course_subjects_changed, sender=Course.subjects.through)

        draft_course = CourseFactory(draft=True)
        non_draft_course = CourseFactory(draft_version=draft_course, key=draft_course.key)
        course_timestamp = draft_course.data_modified_timestamp
        subject_1 = factories.SubjectFactory()
        subject_2 = factories.SubjectFactory()
        subject_3 = factories.SubjectFactory()
        non_draft_course.subjects.add(subject_1, subject_2, subject_3)

        with LogCapture(LOGGER_NAME) as log:
            draft_course.subjects.set((subject_1, subject_2))
        draft_course.refresh_from_db()
        assert course_timestamp < draft_course.data_modified_timestamp

        log.check_present(
            (
                LOGGER_NAME,
                'INFO',
                f"Subject M2M relation has been updated for course {draft_course.key}."
            )
        )
        m2m_changed.disconnect(course_subjects_changed, sender=Course.subjects.through)

    def test_course_subjects_change__non_draft_missing(self):
        """
        Verify the change in course subjects will not update the data timestamp for Course if course does not
        have a non-draft version.
        """
        m2m_changed.connect(course_subjects_changed, sender=Course.subjects.through)
        course = CourseFactory(draft=True)
        course_timestamp = course.data_modified_timestamp
        subject_1 = factories.SubjectFactory()
        subject_2 = factories.SubjectFactory()

        with LogCapture(LOGGER_NAME) as log:
            course.subjects.set((subject_1, subject_2))
        course.refresh_from_db()
        assert course_timestamp == course.data_modified_timestamp
        with self.assertRaises(AssertionError):
            log.check_present(
                (
                    LOGGER_NAME,
                    'INFO',
                    f"Subject M2M relation has been updated for course {course.key}."
                )
            )

        m2m_changed.disconnect(course_subjects_changed, sender=Course.subjects.through)

    def test_course_run_transcript_language_changed(self):
        """
        Verify the change of transcript language relationship updates the data modified timestamp for related Course.
        """
        m2m_changed.connect(course_run_transcript_languages_changed, sender=CourseRun.transcript_languages.through)
        course = CourseFactory(draft=True)
        course_run = factories.CourseRunFactory(course=course, draft=True)
        language_tags = LanguageTag.objects.all()[:2]
        course_timestamp = course.data_modified_timestamp

        with LogCapture(LOGGER_NAME) as log:
            course_run.transcript_languages.set(language_tags)

        course.refresh_from_db()
        assert course_timestamp < course.data_modified_timestamp
        log.check_present(
            (
                LOGGER_NAME,
                'INFO',
                f"{course_run.transcript_languages.through} has been updated for course run {course_run.key}."
            )
        )

        m2m_changed.disconnect(course_run_transcript_languages_changed, sender=CourseRun.transcript_languages.through)

    def test_course_run_staff_changed__non_draft_present(self):
        """
        Verify the staff relation change in course run updates the timestamp for course if a non-draft course run
        is present.
        """
        m2m_changed.connect(course_run_staff_changed, sender=CourseRun.staff.through)
        draft_course = CourseFactory(draft=True)
        non_draft_course = CourseFactory(draft_version=draft_course, key=draft_course.key)
        draft_course_run = factories.CourseRunFactory(draft=True, course=draft_course)
        non_draft_course_run = factories.CourseRunFactory(
            course=non_draft_course, draft_version=draft_course_run, key=draft_course_run.key
        )
        staff1 = factories.PersonFactory()
        staff2 = factories.PersonFactory()
        staff3 = factories.PersonFactory()
        course_timestamp = draft_course.data_modified_timestamp

        non_draft_course_run.staff.add(staff1, staff2, staff3)

        with LogCapture(LOGGER_NAME) as log:
            draft_course_run.staff.set((staff1, staff2))

        draft_course.refresh_from_db()
        assert course_timestamp < draft_course.data_modified_timestamp
        log.check_present(
            (
                LOGGER_NAME,
                'INFO',
                f"Staff M2M relation has been updated for course run {draft_course_run.key}."
            )
        )
        m2m_changed.disconnect(course_run_staff_changed, sender=CourseRun.staff.through)

    def test_course_run_staff_changed__non_draft_missing(self):
        """
        Verify the staff relation change in course run does not update the timestamp for course if non-draft course run
        is not present.
        """
        m2m_changed.connect(course_run_staff_changed, sender=CourseRun.staff.through)
        draft_course = CourseFactory(draft=True)
        draft_course_run = factories.CourseRunFactory(draft=True, course=draft_course)
        staff1 = factories.PersonFactory()
        staff2 = factories.PersonFactory()
        course_timestamp = draft_course.data_modified_timestamp

        with LogCapture(LOGGER_NAME) as log:
            draft_course_run.staff.set((staff1, staff2))

        draft_course.refresh_from_db()
        assert course_timestamp == draft_course.data_modified_timestamp
        with self.assertRaises(AssertionError):
            log.check_present(
                (
                    LOGGER_NAME,
                    'INFO',
                    f"Staff M2M relation has been updated for course run {draft_course_run.key}."
                )
            )
        m2m_changed.disconnect(course_run_staff_changed, sender=CourseRun.staff.through)
