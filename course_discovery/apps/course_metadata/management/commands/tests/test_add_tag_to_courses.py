import pytest
from django.core.management import CommandError, call_command
from django.test import TestCase

from course_discovery.apps.core.tests.factories import PartnerFactory
from course_discovery.apps.course_metadata.models import Course, TagCourseUuidsConfig
from course_discovery.apps.course_metadata.tests.factories import CourseFactory


class AddTagToCoursesCommandTests(TestCase):
    def setUp(self):
        super().setUp()
        self.partner = PartnerFactory(marketing_site_api_password=None)
        self.course1 = CourseFactory(partner=self.partner)
        self.course2 = CourseFactory(partner=self.partner)
        self.course3 = CourseFactory(partner=self.partner)

    def testNormalRun(self):
        call_command('add_tag_to_courses', "tag0", self.course1.uuid, self.course2.uuid)
        assert Course.objects.filter(topics__name='tag0', uuid=self.course1.uuid).exists()
        assert Course.objects.filter(topics__name='tag0', uuid=self.course2.uuid).exists()
        assert Course.objects.filter(uuid=self.course3.uuid).exists()
        assert not Course.objects.filter(topics__name='tag0', uuid=self.course3.uuid).exists()

    def testMissingArgument(self):
        with pytest.raises(CommandError):
            call_command('add_tag_to_courses', "tag0")

    def testArgsFromDatabase(self):
        config = TagCourseUuidsConfig.get_solo()
        config.tag = 'tag0'
        config.course_uuids = str(self.course1.uuid) + " " + str(self.course2.uuid)
        config.save()
        call_command('add_tag_to_courses', "--args-from-database")
        assert Course.objects.filter(topics__name='tag0', uuid=self.course1.uuid).exists()
        assert Course.objects.filter(topics__name='tag0', uuid=self.course2.uuid).exists()
        assert Course.objects.filter(uuid=self.course3.uuid).exists()
        assert not Course.objects.filter(topics__name='tag0', uuid=self.course3.uuid).exists()

        # test command line args ignored if --args-from-database is set
        call_command('add_tag_to_courses', "tag1", self.course1.uuid, self.course2.uuid, "--args-from-database")
        assert not Course.objects.filter(topics__name='tag1').exists()
