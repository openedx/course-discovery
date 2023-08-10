from unittest import mock

import ddt
from django.core.management import CommandError, call_command
from django.test import TestCase
from testfixtures import LogCapture, StringComparison

from course_discovery.apps.course_metadata.data_loaders.course_type import logger
from course_discovery.apps.course_metadata.models import (
    BackpopulateCourseTypeConfig, Course, CourseRunType, CourseType, Mode, Seat, Track
)
from course_discovery.apps.course_metadata.tests import factories
from course_discovery.apps.course_metadata.utils import ensure_draft_world


@ddt.ddt
class BackpopulateCourseTypeCommandTests(TestCase):
    def setUp(self):
        super().setUp()

        # Disable marketing site password just to save us from having to mock the responses
        self.partner = factories.PartnerFactory(marketing_site_api_password=None)

        # Fill out a bunch of types and modes. Exact mode parameters don't matter, just the resulting seat types.
        self.audit_seat_type = factories.SeatTypeFactory.audit()
        self.verified_seat_type = factories.SeatTypeFactory.verified()
        self.audit_mode = Mode.objects.get(slug=Seat.AUDIT)
        self.verified_mode = Mode.objects.get(slug=Seat.VERIFIED)
        self.audit_track = Track.objects.get(seat_type=self.audit_seat_type, mode=self.audit_mode)
        self.verified_track = Track.objects.get(seat_type=self.verified_seat_type, mode=self.verified_mode)
        self.empty_run_type = CourseRunType.objects.get(slug=CourseRunType.EMPTY)
        self.audit_run_type = CourseRunType.objects.get(slug=CourseRunType.AUDIT)
        self.va_run_type = CourseRunType.objects.get(slug=CourseRunType.VERIFIED_AUDIT)
        self.empty_course_type = CourseType.objects.get(slug=CourseType.EMPTY)
        self.va_course_type = CourseType.objects.get(slug=CourseType.VERIFIED_AUDIT)
        self.audit_course_type = CourseType.objects.get(slug=CourseType.AUDIT)

        # Now create some courses and orgs that will be found to match the above, in the simple happy path case.
        self.org = factories.OrganizationFactory(partner=self.partner, key='Org1')
        self.course = factories.CourseFactory(partner=self.partner, authoring_organizations=[self.org],
                                              type=self.empty_course_type,
                                              key=f'{self.org.key}+Course1')
        self.entitlement = factories.CourseEntitlementFactory(partner=self.partner, course=self.course,
                                                              mode=self.verified_seat_type)
        self.audit_run = factories.CourseRunFactory(course=self.course, type=self.empty_run_type,
                                                    key='course-v1:Org1+Course1+A')
        self.audit_seat = factories.SeatFactory(course_run=self.audit_run, type=self.audit_seat_type)
        self.verified_run = factories.CourseRunFactory(course=self.course, type=self.empty_run_type,
                                                       key='course-v1:Org1+Course1+V')
        self.verified_seat = factories.SeatFactory(course_run=self.verified_run, type=self.verified_seat_type)
        self.verified_audit_seat = factories.SeatFactory(course_run=self.verified_run, type=self.audit_seat_type)

        # Create parallel obj / course for argument testing
        self.org2 = factories.OrganizationFactory(partner=self.partner, key='Org2')
        self.org3 = factories.OrganizationFactory(partner=self.partner, key='Org3')
        self.course2 = factories.CourseFactory(partner=self.partner, authoring_organizations=[self.org2, self.org3],
                                               type=self.empty_course_type,
                                               key=f'{self.org2.key}+Course1')
        self.c2_audit_run = factories.CourseRunFactory(course=self.course2, type=self.empty_run_type)
        self.c2_audit_seat = factories.SeatFactory(course_run=self.c2_audit_run, type=self.audit_seat_type)

    def run_command(self, courses=None, orgs=None, allow_for=None, commit=True, fails=None, log=None):
        command_args = ['--partner=' + self.partner.short_code]
        if commit:
            command_args.append('--commit')
        if courses is None and orgs is None:
            courses = [self.course]
        if courses:
            command_args += ['--course=' + str(c.uuid) for c in courses]
        if orgs:
            command_args += ['--org=' + str(o.key) for o in orgs]
        if allow_for:
            command_args += ['--allow-for=' + type_slug_run_slug_tuple for type_slug_run_slug_tuple in allow_for]

        with LogCapture(logger.name) as log_capture:
            if fails:
                fails = fails if isinstance(fails, list) else [fails]
                keys = sorted(f'{fail.key} ({fail.id})' for fail in fails)
                msg = 'Could not backpopulate a course type for the following courses: {course_keys}'.format(
                    course_keys=', '.join(keys)
                )
                with self.assertRaisesMessage(CommandError, msg):
                    self.call_command(*command_args)
            else:
                self.call_command(*command_args)

        if log:
            log_capture.check_present((logger.name, 'INFO', StringComparison(log)))

        # As a convenience, refresh our built in courses and runs
        for obj in (self.course, self.audit_run, self.verified_run, self.course2, self.c2_audit_run):
            if obj.id:
                obj.refresh_from_db()

    def call_command(self, *args):
        call_command('backpopulate_course_type', *args)

    def test_invalid_args(self):
        partner_code = f'--partner={self.partner.short_code}'
        course_arg = f'--course={self.course.uuid}'

        with self.assertRaises(CommandError) as cm:
            self.call_command(partner_code)  # no courses listed
        self.assertEqual(cm.exception.args[0], 'No courses found. Did you specify an argument?')

        with self.assertRaises(CommandError) as cm:
            self.call_command(course_arg)  # no partner
        self.assertEqual(cm.exception.args[0], 'You must specify --partner')

        with self.assertRaises(CommandError) as cm:
            self.call_command('--partner=NotAPartner', course_arg)
        self.assertEqual(cm.exception.args[0], 'No courses found. Did you specify an argument?')

        with self.assertRaises(CommandError) as cm:
            self.call_command('--allow-for=NotACourseType:audit', partner_code, course_arg)
        self.assertEqual(cm.exception.args[0], 'Supplied Course Type slug [NotACourseType] does not exist.')

        with self.assertRaises(CommandError) as cm:
            self.call_command('--allow-for=verified-audit:NotACourseRunType', partner_code, course_arg)
        self.assertEqual(cm.exception.args[0], 'Supplied Course Run Type slug [NotACourseRunType] does not exist.')

    def test_args_from_database(self):
        config = BackpopulateCourseTypeConfig.get_solo()
        config.arguments = '--partner=a --course=b --course=c --org=d --org=e --commit'
        config.save()

        module = 'course_discovery.apps.course_metadata.management.commands.backpopulate_course_type'

        # First ensure we do correctly grab arguments from the db
        with mock.patch(module + '.Command.backpopulate') as cm:
            self.call_command('--args-from-database', '--course=f')
        self.assertEqual(cm.call_count, 1)
        args = cm.call_args[0][0]
        self.assertEqual(args['partner'], 'a')
        self.assertEqual(args['commit'], True)
        self.assertEqual(args['course'], ['b', 'c'])
        self.assertEqual(args['org'], ['d', 'e'])

        # Then confirm that we don't when not asked to
        with mock.patch(module + '.Command.backpopulate') as cm:
            self.call_command('--partner=b', '--course=f')
        self.assertEqual(cm.call_count, 1)
        args = cm.call_args[0][0]
        self.assertEqual(args['partner'], 'b')
        self.assertEqual(args['commit'], False)
        self.assertEqual(args['course'], ['f'])
        self.assertEqual(args['org'], [])

    def test_non_committal_run(self):
        self.run_command(commit=False)
        self.assertTrue(self.course.type.empty)

        # Sanity check that it would set the type with commit=True
        self.run_command()
        self.assertFalse(self.course.type.empty)

    def test_normal_run(self):
        self.run_command(log='Course .* matched type Verified and Audit')
        self.assertEqual(self.course.type, self.va_course_type)
        self.assertEqual(self.audit_run.type, self.audit_run_type)
        self.assertEqual(self.verified_run.type, self.va_run_type)

    def test_existing_type(self):
        # First, confirm we try and fail to find a valid match for runs when course has type but no runs can match it
        prof_course_type = CourseType.objects.get(slug=CourseType.PROFESSIONAL)
        self.course.type = prof_course_type
        self.course.save()
        self.run_command(fails=self.course,
                         log="Existing course type Professional Only for .* doesn't match its own entitlements")

        # Now set up the runs with types too -- but make sure we don't consider the course type a valid match yet
        self.entitlement.delete()
        audit_run_type = CourseRunType.objects.get(slug=CourseRunType.AUDIT)
        self.audit_run.type = audit_run_type
        self.audit_run.save()
        self.verified_run.type = audit_run_type
        self.verified_run.save()
        self.run_command(fails=self.course,
                         log="Existing run type Audit Only for .* doesn't match course type Professional Only")

        # Once the run type is valid for the course type, it should still require matching seats.
        prof_course_type.course_run_types.add(audit_run_type)
        self.run_command(fails=self.course, log="Existing run type Audit Only for .* doesn't match its own seats")

        # Now make the runs match the audit only run types and everything should pass
        self.verified_seat.delete()
        pre_course_modified = self.course.modified
        pre_audit_modified = self.audit_run.modified
        pre_verified_modified = self.verified_run.modified
        self.run_command()
        self.assertEqual(self.course.type, prof_course_type)
        self.assertEqual(self.course.modified, pre_course_modified)
        self.assertEqual(self.audit_run.type, audit_run_type)
        self.assertEqual(self.audit_run.modified, pre_audit_modified)
        self.assertEqual(self.verified_run.type, audit_run_type)
        self.assertEqual(self.verified_run.modified, pre_verified_modified)

    def test_affects_drafts_too(self):
        draft_course = ensure_draft_world(Course.objects.get(pk=self.course.pk))

        self.run_command()
        draft_course.refresh_from_db()
        self.assertEqual(self.course.type, self.va_course_type)
        self.assertEqual(self.audit_run.type, self.audit_run_type)
        self.assertEqual(self.verified_run.type, self.va_run_type)
        self.assertEqual(draft_course.type, self.va_course_type)
        self.assertEqual(set(draft_course.course_runs.values_list('type', flat=True)),
                         {self.audit_run_type.id, self.va_run_type.id})

    def test_matches_earliest_course_type(self):
        # This messes up this test due to Verified and Audit being a subset of Credit
        # and Credit being created prior to 'Second'
        CourseType.objects.get(slug=CourseType.CREDIT_VERIFIED_AUDIT).delete()
        second_type = factories.CourseTypeFactory(
            name='Second',
            entitlement_types=self.va_course_type.entitlement_types.all(),
            course_run_types=self.va_course_type.course_run_types.all(),
        )

        self.run_command()
        self.assertEqual(self.course.type, self.va_course_type)

        # Now sanity check that we *would* have matched
        self.course.type = self.empty_course_type
        self.course.save()
        self.va_course_type.delete()
        self.run_command()
        self.assertEqual(self.course.type, second_type)

    def test_one_mismatched_run_ruins_whole_thing(self):
        """ Test that a single run that doesn't match its parent course type will prevent a course match. """
        self.audit_seat.delete()
        self.run_command(fails=self.course)
        self.assertTrue(self.course.type.empty)

        # Now sanity check that we *would* have matched without seatless run
        self.audit_run.delete()
        self.run_command()
        self.assertEqual(self.course.type, self.va_course_type)

    def test_by_org(self):
        self.run_command(orgs=[self.org2])
        self.assertTrue(self.course.type.empty)
        self.assertEqual(self.course2.type, self.audit_course_type)

    def test_by_multiple_orgs(self):
        self.run_command(orgs=[self.org, self.org3])
        self.assertEqual(self.course.type, self.va_course_type)
        self.assertEqual(self.course2.type, self.audit_course_type)

    def test_by_multiple_courses(self):
        self.run_command(courses=[self.course, self.course2])
        self.assertEqual(self.course.type, self.va_course_type)
        self.assertEqual(self.course2.type, self.audit_course_type)

    def test_by_course_and_org(self):
        self.run_command(courses=[self.course], orgs=[self.org2])
        self.assertEqual(self.course.type, self.va_course_type)
        self.assertEqual(self.course2.type, self.audit_course_type)

    def test_courses_with_honor_seats(self):
        honor_seat_type = factories.SeatTypeFactory.honor()
        honor_run_type = CourseRunType.objects.get(slug=CourseRunType.HONOR)
        # Tests that Honor Only will not match with Verified and Honor despite being a subset of that CourseRunType
        honor_run = factories.CourseRunFactory(course=self.course, type=self.empty_run_type,
                                               key='course-v1:Org1+Course1+H')
        factories.SeatFactory(course_run=honor_run, type=honor_seat_type)

        vh_run_type = CourseRunType.objects.get(slug=CourseRunType.VERIFIED_HONOR)
        vh_run = factories.CourseRunFactory(course=self.course, type=self.empty_run_type,
                                            key='course-v1:Org1+Course1+VH')
        factories.SeatFactory(course_run=vh_run, type=honor_seat_type)
        factories.SeatFactory(course_run=vh_run, type=self.verified_seat_type)

        allow_for = [
            CourseType.VERIFIED_AUDIT + ':' + CourseRunType.HONOR,
            CourseType.VERIFIED_AUDIT + ':' + CourseRunType.VERIFIED_HONOR
        ]
        self.run_command(allow_for=allow_for)
        self.assertEqual(self.course.type, self.va_course_type)
        honor_run.refresh_from_db()
        self.assertEqual(honor_run.type, honor_run_type)
        vh_run.refresh_from_db()
        self.assertEqual(vh_run.type, vh_run_type)

    def test_course_runs_with_no_seats(self):
        print(CourseRunType.objects.all())
        empty_run_type = CourseRunType.objects.get(slug=CourseRunType.EMPTY)
        empty_run = factories.CourseRunFactory(course=self.course, type=self.empty_run_type,
                                               key='course-v1:Org1+Course1+H')
        self.assertEqual(empty_run.seats.count(), 0)

        allow_for = [CourseType.VERIFIED_AUDIT + ':' + CourseRunType.EMPTY]
        self.run_command(allow_for=allow_for)
        self.assertEqual(self.course.type, self.va_course_type)
        empty_run.refresh_from_db()
        self.assertEqual(empty_run.type, empty_run_type)
