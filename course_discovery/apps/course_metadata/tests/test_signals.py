import datetime
from re import escape
from unittest import mock

import ddt
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
    BackfillCourseRunSlugsConfig, BackpopulateCourseTypeConfig, BulkModifyProgramHookConfig, BulkUpdateImagesConfig,
    CourseRun, Curriculum, CurriculumProgramMembership, DataLoaderConfig, DeletePersonDupsConfig,
    DrupalPublishUuidConfig, LevelTypeTranslation, MigratePublisherToCourseMetadataConfig, ProfileImageDownloadConfig,
    Program, ProgramTypeTranslation, RemoveRedirectsConfig, SubjectTranslation, TagCourseUuidsConfig, TopicTranslation
)
from course_discovery.apps.course_metadata.signals import _duplicate_external_key_message
from course_discovery.apps.course_metadata.tests import factories

LOGGER_NAME = 'course_discovery.apps.course_metadata.signals'



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
