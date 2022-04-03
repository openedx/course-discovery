import ddt
import pytest
from django.core.management import CommandError, call_command
from django.test import TestCase

from course_discovery.apps.course_metadata.tests.factories import (
    CourseFactory, CourseSkillsFactory, SkillFactory, SubjectFactory
)
from course_discovery.apps.taxonomy_support.models import CourseRecommendation, UpdateCourseRecommendationsConfig


@ddt.ddt
class UpdateCourseRecommendationsCommandTests(TestCase):
    LOGGER = 'course_discovery.apps.taxonomy_support.management.commands.update_course_recommendations.logger'

    def setUp(self):
        super().setUp()

        self.course1 = CourseFactory(
            subjects=SubjectFactory.create_batch(3),
            draft=False
        )
        self.course2 = CourseFactory(
            subjects=SubjectFactory.create_batch(3),
            draft=False
        )
        self.course3 = CourseFactory(
            subjects=SubjectFactory.create_batch(3),
            draft=False
        )
        skill1 = SkillFactory()
        skill2 = SkillFactory()
        skill3 = SkillFactory()
        CourseSkillsFactory(course_key=self.course1.key, skill=skill1)
        CourseSkillsFactory(course_key=self.course1.key, skill=skill2)
        CourseSkillsFactory(course_key=self.course2.key, skill=skill1)
        CourseSkillsFactory(course_key=self.course2.key, skill=skill2)
        CourseSkillsFactory(course_key=self.course2.key, skill=skill3)
        CourseSkillsFactory(course_key=self.course3.key)

    def test_missing_arguments(self):
        with pytest.raises(CommandError):
            call_command('update_course_recommendations')

    def test_conflicting_arguments(self):
        with pytest.raises(CommandError):
            call_command('update_course_recommendations', '--args-from-database', '--all')
        with pytest.raises(CommandError):
            call_command('update_course_recommendations', '--all', '-uuids', self.course1.uuid)
        with pytest.raises(CommandError):
            call_command('update_course_recommendations', '-uuids', self.course1.uuid, '--args-from-database')

    @ddt.data(
        ('command_line', '--all'),
        ('database', '--args-from-database'),
    )
    @ddt.unpack
    def test_update_recommendations_all(self, argument_source, argument):
        if argument_source == 'database':
            config = UpdateCourseRecommendationsConfig.get_solo()
            config.all_courses = True
            config.save()
        call_command('update_course_recommendations', argument)
        course_recommendations_count = CourseRecommendation.objects.all().count()
        self.assertEqual(course_recommendations_count, 2)

    @ddt.data('command_line', 'database',)
    def test_update_recommendations_specific_course(self, argument_source):

        if argument_source == 'database':
            config = UpdateCourseRecommendationsConfig.get_solo()
            config.uuids = self.course1.uuid
            config.save()
            call_command('update_course_recommendations', '--args-from-database')
        else:
            call_command('update_course_recommendations', '-uuids', self.course1.uuid)
        course_recommendations_count = CourseRecommendation.objects.all().count()
        self.assertEqual(course_recommendations_count, 1)
