from unittest.mock import patch

from django.test import TestCase

from course_discovery.apps.course_metadata.management.commands.backfill_enterprise_inclusion import Command
from course_discovery.apps.course_metadata.models import Course, Organization
from course_discovery.apps.course_metadata.tests.factories import CourseFactory, OrganizationFactory


class BackfillEnterpriseInclusion(TestCase):
    def setUp(self):
        super().setUp()
        self.org_1, self.org_2 = OrganizationFactory.create_batch(2)
        self.course_1 = CourseFactory(authoring_organizations=[self.org_1])
        self.course_2 = CourseFactory(authoring_organizations=[self.org_1])
        self.course_3 = CourseFactory(authoring_organizations=[self.org_2])
        self.course_4 = CourseFactory(
            authoring_organizations=[
                self.org_1, self.org_2])
        self.org_test_data = [str(self.org_1.uuid)]
        self.course_test_data = [
            self.course_1.key,
            self.course_3.key,
            self.course_4.key]

    def test_normal_run(self):
        uuid_path = 'course_discovery.apps.course_metadata.management.commands.backfill_enterprise_inclusion.org_uuids'
        key_path = 'course_discovery.apps.course_metadata.management.commands.backfill_enterprise_inclusion.course_keys'

        with patch(uuid_path, self.org_test_data):
            with patch(key_path, self.course_test_data):
                Command().handle()

        org_1 = Organization.objects.filter(uuid=self.org_1.uuid).first()
        org_2 = Organization.objects.filter(uuid=self.org_2.uuid).first()
        assert org_1.enterprise_subscription_inclusion is True
        assert org_2.enterprise_subscription_inclusion is False

        course_1 = Course.objects.filter(uuid=self.course_1.uuid).first()
        course_2 = Course.objects.filter(uuid=self.course_2.uuid).first()
        course_3 = Course.objects.filter(uuid=self.course_3.uuid).first()
        course_4 = Course.objects.filter(uuid=self.course_4.uuid).first()

        # org and course both true
        assert course_1.enterprise_subscription_inclusion is True
        # org true but course false
        assert course_2.enterprise_subscription_inclusion is False
        # org false but course true
        assert course_3.enterprise_subscription_inclusion is False
        # one org true, but one org not, course true
        assert course_4.enterprise_subscription_inclusion is False
