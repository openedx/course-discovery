from unittest import mock

from django.core.exceptions import ValidationError
from django.core.management import CommandError, call_command
from django.test import TestCase

from course_discovery.apps.core.models import Partner
from course_discovery.apps.course_metadata.models import (
    CourseRun, DeletePersonDupsConfig, Endorsement, Person, PersonSocialNetwork, Position, Program
)
from course_discovery.apps.course_metadata.tests import factories


class DeletePersonDupsCommandTests(TestCase):
    def setUp(self):
        super().setUp()
        # Disable marketing site password just to save us from having to mock the responses
        self.partner = factories.PartnerFactory(marketing_site_api_password=None)
        self.person = factories.PersonFactory(partner=self.partner, given_name='Person')
        self.target = factories.PersonFactory(partner=self.partner, given_name='Target')
        self.instructor1 = factories.PersonFactory(partner=self.partner, given_name='Instructor1')
        self.instructor2 = factories.PersonFactory(partner=self.partner, given_name='Instructor2')
        self.instructor3 = factories.PersonFactory(partner=self.partner, given_name='Instructor3')
        self.position = factories.PositionFactory(person=self.person)
        self.social1 = factories.PersonSocialNetworkFactory(person=self.person)
        self.social2 = factories.PersonSocialNetworkFactory(person=self.person)
        self.endorsement = factories.EndorsementFactory(endorser=self.person)
        self.course = factories.CourseFactory(partner=self.partner)
        self.courserun1 = factories.CourseRunFactory(course=self.course, staff=[
            self.instructor1, self.person, self.instructor2, self.instructor3,
        ])
        self.courserun2 = factories.CourseRunFactory(course=self.course, staff=[
            self.instructor1, self.instructor2, self.person, self.instructor3,
        ])
        self.program = factories.ProgramFactory(courses=[self.course], instructor_ordering=[
            self.person, self.instructor1, self.instructor2, self.instructor3,
        ])

    def run_command(self, people=None, commit=True):
        command_args = ['--partner-code=' + self.partner.short_code]
        if commit:
            command_args.append('--commit')
        if people is None:
            people = [(self.person, self.target)]
        command_args += [str(a.uuid) + ':' + str(b.uuid) for (a, b) in people]
        self.call_command(*command_args)

    def call_command(self, *args):
        call_command('delete_person_dups', *args)

    def test_invalid_args(self):
        partner_code = f'--partner-code={self.partner.short_code}'
        uuid_arg = f'{self.person.uuid}:{self.target.uuid}'

        with self.assertRaises(CommandError) as cm:
            self.call_command(partner_code)  # no uuid
        self.assertEqual(cm.exception.args[0], 'You must specify at least one person')

        with self.assertRaises(CommandError) as cm:
            self.call_command(uuid_arg)  # no partner
        self.assertEqual(cm.exception.args[0], 'You must specify --partner-code')

        with self.assertRaises(Partner.DoesNotExist):
            self.call_command('--partner=NotAPartner', uuid_arg)

        with self.assertRaises(CommandError) as cm:
            self.call_command(partner_code, 'a')
        self.assertEqual(cm.exception.args[0], 'Malformed argument "a", should be in form of UUID:TARGET_UUID')

        with self.assertRaises(CommandError) as cm:
            self.call_command(partner_code, 'a:a')
        self.assertEqual(cm.exception.args[0], 'Malformed argument "a:a", UUIDs cannot be equal')

        with self.assertRaises(ValidationError):
            self.call_command(partner_code, 'a:b')

        with self.assertRaises(Person.DoesNotExist):
            self.call_command(partner_code, '00000000-0000-0000-0000-000000000000:00000000-0000-0000-0000-000000000001')

    def test_non_committal_run(self):
        self.run_command(commit=False)

        # Now everything in the db should be the same (still exist)
        Person.objects.get(uuid=self.person.uuid)  # will raise if it doesn't exist

        # Spot check one course run just to feel a little more confident
        self.assertEqual(CourseRun.objects.get(id=self.courserun1.id).staff, self.courserun1.staff)

    def test_remove_from_marketing(self):
        method = 'course_discovery.apps.course_metadata.people.MarketingSitePeople.delete_person_by_uuid'

        with mock.patch(method) as cm:
            self.run_command()
        self.assertEqual(cm.call_count, 1)
        args = cm.call_args[0]
        self.assertEqual(args[0], self.person.partner)
        self.assertEqual(args[1], self.person.uuid)

    def test_normal_run(self):
        self.run_command()

        # Straight deleted
        self.assertEqual(Person.objects.filter(id=self.person.id).count(), 0)
        self.assertEqual(Position.objects.filter(id=self.position.id).count(), 0)
        self.assertEqual(PersonSocialNetwork.objects.filter(id=self.social1.id).count(), 0)
        self.assertEqual(PersonSocialNetwork.objects.filter(id=self.social2.id).count(), 0)

        # Migrated
        self.assertEqual(Endorsement.objects.get(id=self.endorsement.id).endorser, self.target)
        self.assertListEqual(list(CourseRun.objects.get(id=self.courserun1.id).staff.all()), [
            self.instructor1, self.target, self.instructor2, self.instructor3,
        ])
        self.assertListEqual(list(CourseRun.objects.get(id=self.courserun2.id).staff.all()), [
            self.instructor1, self.instructor2, self.target, self.instructor3,
        ])
        self.assertListEqual(list(Program.objects.get(id=self.program.id).instructor_ordering.all()), [
            self.target, self.instructor1, self.instructor2, self.instructor3,
        ])

    def test_target_already_present(self):
        # Change everything to include target. We expect that target's place isn't altered.
        self.courserun1.staff.set(list(self.courserun1.staff.all()) + [self.target])
        self.courserun2.staff.set(list(self.courserun2.staff.all()) + [self.target])
        self.program.instructor_ordering.set(list(self.program.instructor_ordering.all()) + [self.target])

        expected = [self.instructor1, self.instructor2, self.instructor3, self.target]

        self.run_command()

        self.assertListEqual(list(CourseRun.objects.get(id=self.courserun1.id).staff.all()), expected)
        self.assertListEqual(list(CourseRun.objects.get(id=self.courserun2.id).staff.all()), expected)
        self.assertListEqual(list(Program.objects.get(id=self.program.id).instructor_ordering.all()), expected)

    def test_multiple_people(self):
        self.run_command(people=[(self.person, self.target), (self.instructor1, self.instructor2)])

        # Straight deleted
        self.assertEqual(Person.objects.filter(id=self.person.id).count(), 0)
        self.assertEqual(Person.objects.filter(id=self.instructor1.id).count(), 0)
        self.assertEqual(Position.objects.filter(id=self.position.id).count(), 0)
        self.assertEqual(PersonSocialNetwork.objects.filter(id=self.social1.id).count(), 0)
        self.assertEqual(PersonSocialNetwork.objects.filter(id=self.social2.id).count(), 0)

        # Migrated
        self.assertEqual(Endorsement.objects.get(id=self.endorsement.id).endorser, self.target)
        self.assertListEqual(list(CourseRun.objects.get(id=self.courserun1.id).staff.all()), [
            self.target, self.instructor2, self.instructor3,
        ])
        self.assertListEqual(list(CourseRun.objects.get(id=self.courserun2.id).staff.all()), [
            self.instructor2, self.target, self.instructor3,
        ])
        self.assertListEqual(list(Program.objects.get(id=self.program.id).instructor_ordering.all()), [
            self.target, self.instructor2, self.instructor3,
        ])

    def test_args_from_database(self):
        config = DeletePersonDupsConfig.get_solo()
        config.arguments = '--partner-code=a a:b --commit'
        config.save()

        module = 'course_discovery.apps.course_metadata.management.commands.delete_person_dups'

        # First ensure we do correctly grab arguments from the db
        with mock.patch(module + '.Command.delete_person_dups') as cm:
            self.call_command('--args-from-database', '--partner-code=b', 'c:d')
        self.assertEqual(cm.call_count, 1)
        args = cm.call_args[0][0]
        self.assertEqual(args['partner_code'], 'a')
        self.assertEqual(args['commit'], True)
        self.assertEqual(args['people'], ['a:b'])

        # Then confirm that we don't when not asked to
        with mock.patch(module + '.Command.delete_person_dups') as cm:
            self.call_command('--partner-code=b', 'c:d')
        self.assertEqual(cm.call_count, 1)
        args = cm.call_args[0][0]
        self.assertEqual(args['partner_code'], 'b')
        self.assertEqual(args['commit'], False)
        self.assertEqual(args['people'], ['c:d'])
