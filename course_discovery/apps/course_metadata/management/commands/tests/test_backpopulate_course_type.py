import ddt
import mock
from django.core.management import CommandError, call_command
from django.test import TestCase
from testfixtures import LogCapture, StringComparison

from course_discovery.apps.course_metadata.management.commands.backpopulate_course_type import logger
from course_discovery.apps.course_metadata.models import (
    BackpopulateCourseTypeConfig, Course, CourseRunType, CourseType, Seat, SeatType
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
        self.audit_seat_type = SeatType.objects.get(slug=Seat.AUDIT)
        self.verified_seat_type = SeatType.objects.get(slug=Seat.VERIFIED)
        self.audit_mode = factories.ModeFactory(name='Audit')
        self.verified_mode = factories.ModeFactory(name='Verified')
        self.audit_track = factories.TrackFactory(seat_type=self.audit_seat_type, mode=self.audit_mode)
        self.verified_track = factories.TrackFactory(seat_type=self.verified_seat_type, mode=self.verified_mode)
        self.audit_run_type = factories.CourseRunTypeFactory(name='Audit Only', tracks=[self.audit_track])
        self.va_run_type = factories.CourseRunTypeFactory(name='Verified & Audit',
                                                          tracks=[self.audit_track, self.verified_track])
        self.va_course_type = factories.CourseTypeFactory(name='Verified & Audit',
                                                          entitlement_types=[self.verified_seat_type],
                                                          course_run_types=[self.audit_run_type, self.va_run_type])

        # Now create some courses and orgs that will be found to match the above, in the simple happy path case.
        self.org = factories.OrganizationFactory(partner=self.partner, key='Org1')
        self.course = factories.CourseFactory(partner=self.partner, authoring_organizations=[self.org], type=None,
                                              key='{org}+Course1'.format(org=self.org.key))
        self.entitlement = factories.CourseEntitlementFactory(partner=self.partner, course=self.course,
                                                              mode=self.verified_seat_type)
        self.audit_run = factories.CourseRunFactory(course=self.course, type=None, key='course-v1:Org1+Course1+A')
        self.audit_seat = factories.SeatFactory(course_run=self.audit_run, type=Seat.AUDIT)
        self.verified_run = factories.CourseRunFactory(course=self.course, type=None, key='course-v1:Org1+Course1+V')
        self.verified_seat = factories.SeatFactory(course_run=self.verified_run, type=Seat.VERIFIED)
        self.verified_audit_seat = factories.SeatFactory(course_run=self.verified_run, type=Seat.AUDIT)

        # Create parallel obj / course for argument testing
        self.org2 = factories.OrganizationFactory(partner=self.partner, key='Org2')
        self.org3 = factories.OrganizationFactory(partner=self.partner, key='Org3')
        self.course2 = factories.CourseFactory(partner=self.partner, authoring_organizations=[self.org2, self.org3],
                                               type=None, key='{org}+Course1'.format(org=self.org2.key))
        self.c2_audit_run = factories.CourseRunFactory(course=self.course2, type=None)
        self.c2_audit_seat = factories.SeatFactory(course_run=self.c2_audit_run, type=Seat.AUDIT)

    def run_command(self, courses=None, orgs=None, commit=True, fails=None, log=None):
        command_args = ['--partner=' + self.partner.short_code]
        if commit:
            command_args.append('--commit')
        if courses is None and orgs is None:
            courses = [self.course]
        if courses:
            command_args += ['--course=' + str(c.uuid) for c in courses]
        if orgs:
            command_args += ['--org=' + str(o.key) for o in orgs]

        with LogCapture(logger.name) as log_capture:
            if fails:
                fails = fails if isinstance(fails, list) else [fails]
                keys = sorted('{key} ({id})'.format(key=fail.key, id=fail.id) for fail in fails)
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
        partner_code = '--partner={}'.format(self.partner.short_code)
        course_arg = '--course={}'.format(self.course.uuid)

        with self.assertRaises(CommandError) as cm:
            self.call_command(partner_code)  # no courses listed
        self.assertEqual(cm.exception.args[0], 'No courses found. Did you specify an argument?')

        with self.assertRaises(CommandError) as cm:
            self.call_command(course_arg)  # no partner
        self.assertEqual(cm.exception.args[0], 'Error: the following arguments are required: --partner')

        with self.assertRaises(CommandError) as cm:
            self.call_command('--partner=NotAPartner', course_arg)
        self.assertEqual(cm.exception.args[0], 'No courses found. Did you specify an argument?')

    def test_args_from_database(self):
        config = BackpopulateCourseTypeConfig.get_solo()
        config.arguments = '--partner=a --course=b --course=c --org=d --org=e --commit'
        config.save()

        module = 'course_discovery.apps.course_metadata.management.commands.backpopulate_course_type'

        # First ensure we do correctly grab arguments from the db
        with mock.patch(module + '.Command.backpopulate') as cm:
            self.call_command('--args-from-database', '--partner=b', '--course=f')
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
        self.assertIsNone(self.course.type)

        # Sanity check that it would set the type with commit=True
        self.run_command()
        self.assertIsNotNone(self.course.type)

    def test_normal_run(self):
        self.run_command(log='Course .* matched type Verified & Audit')
        self.assertEqual(self.course.type, self.va_course_type)
        self.assertEqual(self.audit_run.type, self.audit_run_type)
        self.assertEqual(self.verified_run.type, self.va_run_type)

    def test_existing_type(self):
        # First, confirm we try and fail to find a valid match for runs when course has type but no runs can match it
        empty_course_type = CourseType.objects.create(name='Empty')
        self.course.type = empty_course_type
        self.course.save()
        self.run_command(fails=self.course, log="Existing course type Empty for .* doesn't match its own entitlements")

        # Now set up the runs with types too -- but make sure we don't consider the course type a valid match yet
        self.entitlement.delete()
        empty_run_type = CourseRunType.objects.create(name='Empty Run')
        self.audit_run.type = empty_run_type
        self.audit_run.save()
        self.verified_run.type = empty_run_type
        self.verified_run.save()
        self.run_command(fails=self.course, log="Existing run type Empty Run for .* doesn't match course type Empty")

        # Once the run type is valid for the course type, it should still require matching seats.
        empty_course_type.course_run_types.add(empty_run_type)
        self.run_command(fails=self.course, log="Existing run type Empty Run for .* doesn't match its own seats")

        # Now make the runs match the empty run types and everything should pass
        self.audit_seat.delete()
        self.verified_seat.delete()
        self.verified_audit_seat.delete()
        pre_course_modified = self.course.modified
        pre_audit_modified = self.audit_run.modified
        pre_verified_modified = self.verified_run.modified
        self.run_command()
        self.assertEqual(self.course.type, empty_course_type)
        self.assertEqual(self.course.modified, pre_course_modified)
        self.assertEqual(self.audit_run.type, empty_run_type)
        self.assertEqual(self.audit_run.modified, pre_audit_modified)
        self.assertEqual(self.verified_run.type, empty_run_type)
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
        second_type = factories.CourseTypeFactory(
            name='Second',
            entitlement_types=self.va_course_type.entitlement_types.all(),  # pylint: disable=no-member
            course_run_types=self.va_course_type.course_run_types.all(),  # pylint: disable=no-member
        )

        self.run_command()
        self.assertEqual(self.course.type, self.va_course_type)

        # Now sanity check that we *would* have matched
        self.course.type = None
        self.course.save()
        self.va_course_type.delete()
        self.run_command()
        self.assertEqual(self.course.type, second_type)

    def test_one_mismatched_run_ruins_whole_thing(self):
        """ Test that a single run that doesn't match its parent course type will prevent a course match. """
        self.audit_seat.delete()
        self.run_command(fails=self.course)
        self.assertIsNone(self.course.type)

        # Now sanity check that we *would* have matched without seatless run
        self.audit_run.delete()
        self.run_command()
        self.assertEqual(self.course.type, self.va_course_type)

    def test_by_org(self):
        self.run_command(orgs=[self.org2])
        self.assertIsNone(self.course.type)
        self.assertEqual(self.course2.type, self.va_course_type)

    def test_by_multiple_orgs(self):
        self.run_command(orgs=[self.org, self.org3])
        self.assertEqual(self.course.type, self.va_course_type)
        self.assertEqual(self.course2.type, self.va_course_type)

    def test_by_multiple_courses(self):
        self.run_command(courses=[self.course, self.course2])
        self.assertEqual(self.course.type, self.va_course_type)
        self.assertEqual(self.course2.type, self.va_course_type)

    def test_by_course_and_org(self):
        self.run_command(courses=[self.course], orgs=[self.org2])
        self.assertEqual(self.course.type, self.va_course_type)
        self.assertEqual(self.course2.type, self.va_course_type)
