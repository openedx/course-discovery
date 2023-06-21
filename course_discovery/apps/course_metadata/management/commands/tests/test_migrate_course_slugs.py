from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management import call_command
from django.test import TestCase
from testfixtures import LogCapture

from course_discovery.apps.course_metadata.tests.factories import (
    CourseFactory, CourseUrlSlugFactory, MigrateCourseSlugConfigurationFactory, OrganizationFactory, PartnerFactory,
    SourceFactory, SubjectFactory
)

LOGGER_PATH = 'course_discovery.apps.course_metadata.management.commands.migrate_course_slugs'


class TestMigrateCourseSlugs(TestCase):
    def setUp(self):
        super().setUp()
        self.slug_update_report = []
        product_source = SourceFactory(slug='edx')
        partner = PartnerFactory()
        self.course1 = CourseFactory(draft=True, product_source=product_source, partner=partner)
        self.course2 = CourseFactory(draft=True, product_source=product_source, partner=partner)
        self.organization = OrganizationFactory(name='test-organization')
        self.subject = SubjectFactory(name='business')

        self.course1.authoring_organizations.add(self.organization)
        self.course1.subjects.add(self.subject)
        self.course2.authoring_organizations.add(self.organization)
        self.course2.subjects.add(self.subject)

        self.course3_draft = CourseFactory(
            draft=True, product_source=product_source, partner=partner, url_slug='test_course'
        )
        course_url_slug = CourseUrlSlugFactory(
            url_slug='test_slug', is_active=True, partner=partner, course=self.course3_draft
        )
        self.course3_draft.url_slug_history.add(course_url_slug)
        self.course3_draft.authoring_organizations.add(self.organization)
        self.course3_draft.subjects.add(self.subject)

        self.course3_non_draft = CourseFactory(
            draft=False, draft_version_id=self.course3_draft.id, uuid=self.course3_draft.uuid,
            product_source=product_source, partner=partner, title='test_course'
        )
        self.course3_non_draft.url_slug_history.add(course_url_slug)
        self.csv_header = 'course_uuids\n'
        self.csv_file_content = self.csv_header + str(self.course1.uuid) + '\n' + str(self.course2.uuid)
        self.csv_file = SimpleUploadedFile(
            name='test.csv',
            content=self.csv_file_content.encode('utf-8'),
            content_type='text/csv'
        )

    def test_migrate_course_slug_success_flow(self):
        with LogCapture(LOGGER_PATH) as log_capture:
            current_slug_course1 = self.course1.active_url_slug
            current_slug_course2 = self.course2.active_url_slug

            call_command(
                'migrate_course_slugs',
                '--course_uuids', self.course1.uuid,
                '--course_uuids', self.course2.uuid,
            )
            log_capture.check_present(
                (
                    LOGGER_PATH,
                    'INFO',
                    f"Updating slug for course with uuid {self.course1.uuid} and title {self.course1.title}, "
                    f"current slug is '{current_slug_course1}'"
                ),
                (
                    LOGGER_PATH,
                    'INFO',
                    f"Updating slug for course with uuid {self.course2.uuid} and title {self.course2.title}, "
                    f"current slug is '{current_slug_course2}'"
                ),
                (
                    LOGGER_PATH,
                    'INFO',
                    f"course_uuid,old_slug,new_slug,error\n"
                    f"{self.course1.uuid},{current_slug_course1},{self.course1.active_url_slug},None\n"
                    f"{self.course2.uuid},{current_slug_course2},{self.course2.active_url_slug},None\n"
                )
            )

            assert self.course1.active_url_slug == f"learn/business/test-organization-{current_slug_course1}"
            assert self.course2.active_url_slug == f"learn/business/test-organization-{current_slug_course2}"

    def test_migrate_course_slug_success_flow__draft_version(self):
        """
        It will update slug of official (non draft) version of the draft course
        """
        with LogCapture(LOGGER_PATH) as log_capture:
            current_slug_course = self.course3_non_draft.active_url_slug
            current_slug_draft_course = self.course3_draft.active_url_slug

            call_command(
                'migrate_course_slugs',
                '--course_uuids', self.course3_draft.uuid,
            )
            log_capture.check_present(
                (
                    LOGGER_PATH,
                    'INFO',
                    f"Updating slug for non-draft course with title {self.course3_non_draft.title} "
                    f"from '{current_slug_course}' to '{self.course3_non_draft.active_url_slug}'"
                ),
                (
                    LOGGER_PATH,
                    'INFO',
                    f"course_uuid,old_slug,new_slug,error\n"
                    f"{self.course3_draft.uuid},{current_slug_draft_course},{self.course3_draft.active_url_slug},None\n"
                )
            )

            expected_slug = f"learn/business/test-organization-{current_slug_draft_course}"
            assert self.course3_draft.active_url_slug == expected_slug
            assert self.course3_non_draft.active_url_slug == expected_slug

    def test_migrate_course_slug_success_flow__file_upload(self):
        MigrateCourseSlugConfigurationFactory(enabled=True, csv_file=self.csv_file, dry_run=False)
        with LogCapture(LOGGER_PATH) as log_capture:
            current_slug_course1 = self.course1.active_url_slug
            current_slug_course2 = self.course2.active_url_slug

            call_command('migrate_course_slugs', '--args_from_database')
            log_capture.check_present(
                (
                    LOGGER_PATH,
                    'INFO',
                    f"Updating slug for course with uuid {self.course1.uuid} and title {self.course1.title}, "
                    f"current slug is '{current_slug_course1}'"
                ),
                (
                    LOGGER_PATH,
                    'INFO',
                    f"Updating slug for course with uuid {self.course2.uuid} and title {self.course2.title}, "
                    f"current slug is '{current_slug_course2}'"
                ),
                (
                    LOGGER_PATH,
                    'INFO',
                    f"course_uuid,old_slug,new_slug,error\n"
                    f"{self.course1.uuid},{current_slug_course1},{self.course1.active_url_slug},None\n"
                    f"{self.course2.uuid},{current_slug_course2},{self.course2.active_url_slug},None\n"
                )
            )

            assert self.course1.active_url_slug == f"learn/business/test-organization-{current_slug_course1}"
            assert self.course2.active_url_slug == f"learn/business/test-organization-{current_slug_course2}"

    def test_migrate_course_slug_success_flow__dry_run(self):
        with LogCapture(LOGGER_PATH) as log_capture:
            current_slug_course1 = self.course1.active_url_slug
            current_slug_course2 = self.course2.active_url_slug

            call_command(
                'migrate_course_slugs',
                '--course_uuids', self.course1.uuid,
                '--course_uuids', self.course2.uuid,
                '--dry_run', True,
            )

            new_slug_prefix = 'learn/business/test-organization'
            log_capture.check_present(
                (
                    LOGGER_PATH,
                    'INFO',
                    f"course_uuid,old_slug,new_slug,error\n"
                    f"{self.course1.uuid},{current_slug_course1},{new_slug_prefix}-{self.course1.active_url_slug},None\n"  # pylint: disable=line-too-long
                    f"{self.course2.uuid},{current_slug_course2},{new_slug_prefix}-{self.course2.active_url_slug},None\n"  # pylint: disable=line-too-long
                )
            )

            assert self.course1.active_url_slug == current_slug_course1
            assert self.course2.active_url_slug == current_slug_course2

    def test_migrate_course_slug_with_missing_subject_and_organization_errors(self):
        with LogCapture(LOGGER_PATH) as log_capture:
            current_slug_course2 = self.course2.active_url_slug

            # If course doesn't have any subject
            self.course2.subjects.clear()
            call_command(
                'migrate_course_slugs',
                '--course_uuids', self.course1.uuid,
                '--course_uuids', self.course2.uuid,
            )
            log_capture.check_present(
                (
                    LOGGER_PATH,
                    'INFO',
                    f"Course with uuid {self.course2.uuid} and title {self.course2.title} does not have any subject"
                )
            )
            assert self.course2.active_url_slug == current_slug_course2

            # Adding subject to the course and removing organization
            self.course2.subjects.add(self.subject)
            self.course2.authoring_organizations.clear()

            call_command(
                'migrate_course_slugs',
                '--course_uuids', self.course1.uuid,
                '--course_uuids', self.course2.uuid,
            )
            # If course does not have any authoring organization
            log_capture.check_present(
                (
                    LOGGER_PATH,
                    'INFO',
                    f"Course with uuid {self.course2.uuid} and title {self.course2.title} does not have any authoring "
                    f"organizations"
                )
            )
            assert self.course2.active_url_slug == current_slug_course2

            # Adding organization to the course
            self.course2.authoring_organizations.add(self.organization)

            call_command(
                'migrate_course_slugs',
                '--course_uuids', self.course1.uuid,
                '--course_uuids', self.course2.uuid,
            )
            log_capture.check_present(
                (
                    LOGGER_PATH,
                    'INFO',
                    f"Course with uuid {self.course1.uuid} and title {self.course1.title} has slug already in correct "
                    f"format '{self.course1.active_url_slug}'"
                )
            )
            assert self.course2.active_url_slug == f"learn/business/test-organization-{current_slug_course2}"
