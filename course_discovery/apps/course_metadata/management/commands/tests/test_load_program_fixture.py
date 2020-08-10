import itertools
import json
import re

import pytest
import responses
from django.contrib.sites.models import Site
from django.core.management import call_command
from django.core.serializers import json as json_serializer
from django.db import IntegrityError
from django.test import TestCase

from course_discovery.apps.core.models import Partner
from course_discovery.apps.course_metadata.models import (
    Course, CourseRun, Curriculum, CurriculumCourseMembership, CurriculumProgramMembership, Organization, Program,
    ProgramType, SeatType
)
from course_discovery.apps.course_metadata.tests.factories import (
    CourseFactory, CourseRunFactory, CurriculumCourseMembershipFactory, CurriculumFactory,
    CurriculumProgramMembershipFactory, OrganizationFactory, PartnerFactory, ProgramFactory, ProgramTypeFactory,
    SeatTypeFactory
)


class TestLoadProgramFixture(TestCase):
    oauth_host = 'http://example.com'
    catalog_host = 'http://discovery-example.com'

    def setUp(self):
        super().setUp()
        self.pk_generator = itertools.count(1)

        stored_site, created = Site.objects.get_or_create(  # pylint: disable=unused-variable
            domain='example.com'
        )
        self.default_partner = Partner.objects.create(
            site=stored_site,
            name='edX',
            short_code='edx'
        )

        SeatType.objects.all().delete()
        ProgramType.objects.all().delete()

        self.partner = PartnerFactory(name='Test')
        self.organization = OrganizationFactory(partner=self.partner)
        self.seat_type_verified = SeatTypeFactory(name='Verified', slug='verified')
        self.program_type_masters = ProgramTypeFactory(
            name='Masters',
            slug='masters',
            applicable_seat_types=[self.seat_type_verified]
        )

        self.program_type_mm = ProgramTypeFactory(
            name='MicroMasters',
            slug='micromasters',
            applicable_seat_types=[self.seat_type_verified]
        )

        self.course = CourseFactory(partner=self.partner, authoring_organizations=[self.organization])
        self.course_run = CourseRunFactory(course=self.course)
        self.program = ProgramFactory(
            type=self.program_type_masters,
            partner=self.partner,
            authoring_organizations=[self.organization]
        )
        self.course_mm = CourseFactory(partner=self.partner, authoring_organizations=[self.organization])
        self.course_run_mm = CourseRunFactory(course=self.course)
        self.program_mm = ProgramFactory(
            type=self.program_type_mm,
            partner=self.partner,
            authoring_organizations=[self.organization],
            courses=[self.course_mm]
        )
        self.curriculum = CurriculumFactory(program=self.program)
        self.curriculum_course_membership = CurriculumCourseMembershipFactory(
            course=self.course, curriculum=self.curriculum
        )
        self.curriculum_program_membership = CurriculumProgramMembershipFactory(
            program=self.program_mm, curriculum=self.curriculum
        )

        self.program_2 = ProgramFactory(
            type=self.program_type_masters,
            partner=self.partner,
            authoring_organizations=[self.organization]
        )

        self._mock_oauth_request()

    def _mock_oauth_request(self):
        responses.add(
            responses.POST,
            f'{self.oauth_host}/oauth2/access_token',
            json={'access_token': 'abcd', 'expires_in': 60},
            status=200,
        )

    def _mock_fixture_response(self, fixture):
        url = re.compile('{catalog_host}/extensions/api/v1/program-fixture/'.format(
            catalog_host=self.catalog_host,
        ))
        responses.add(responses.GET, url, body=fixture, status=200)

    def _call_load_program_fixture(self, program_uuids):
        call_command(
            'load_program_fixture',
            ','.join(program_uuids),
            '--catalog-host', self.catalog_host,
            '--oauth-host', self.oauth_host,
            '--client-id', 'foo',
            '--client-secret', 'bar',
        )

    def _set_up_masters_program_type(self):
        """
        Set DB to have a conflicting program type on load.
        """
        seat_type = SeatTypeFactory(
            name='Something',
            slug='something',
        )
        existing_program_type = ProgramTypeFactory(
            name='Masters',
            name_t='Masters',
            slug='masters',
            applicable_seat_types=[seat_type]
        )
        return existing_program_type

    def reset_db_state(self):
        Partner.objects.all().exclude(short_code='edx').delete()
        SeatType.objects.all().delete()
        Course.objects.all().delete()
        CourseRun.objects.all().delete()
        Curriculum.objects.all().delete()
        CurriculumCourseMembership.objects.all().delete()
        CurriculumProgramMembership.objects.all().delete()
        ProgramType.objects.all().delete()
        Organization.objects.all().delete()
        Program.objects.all().delete()

    @responses.activate
    def test_load_programs(self):

        fixture = json_serializer.Serializer().serialize([
            self.program_type_masters,
            self.program_type_mm,
            self.organization,
            self.seat_type_verified,
            self.program,
            self.program_2,
            self.program_mm,
            self.curriculum_program_membership,
            self.curriculum_course_membership,
            self.curriculum,
            self.course,
            self.course_mm,
            self.course_run,
            self.course_run_mm,
        ])
        self._mock_fixture_response(fixture)

        requested_programs = [
            str(self.program.uuid),
            str(self.program_2.uuid),
        ]
        self.reset_db_state()
        self._call_load_program_fixture(requested_programs)

        # walk through program structure to validate correct
        # objects have been created
        stored_program = Program.objects.get(uuid=self.program.uuid)
        stored_program_2 = Program.objects.get(uuid=self.program_2.uuid)
        self.assertEqual(stored_program.title, self.program.title)
        self.assertEqual(stored_program_2.title, self.program_2.title)

        stored_organization = stored_program.authoring_organizations.first()
        self.assertEqual(stored_organization.name, self.organization.name)

        # partner should use existing edx value
        self.assertEqual(stored_program.partner, self.default_partner)
        self.assertEqual(stored_organization.partner, self.default_partner)

        stored_program_type = stored_program.type
        self.assertEqual(stored_program_type.name_t, self.program_type_masters.name)

        stored_seat_type = stored_program_type.applicable_seat_types.first()
        self.assertEqual(stored_seat_type.name, self.seat_type_verified.name)

        stored_curriculum = stored_program.curricula.first()
        self.assertEqual(stored_curriculum.uuid, self.curriculum.uuid)

        stored_course = stored_curriculum.course_curriculum.first()
        self.assertEqual(stored_course.key, self.course.key)

        stored_mm = stored_curriculum.program_curriculum.first()
        self.assertEqual(stored_mm.uuid, self.program_mm.uuid)

        stored_course_run = stored_course.course_runs.first()
        self.assertEqual(stored_course_run.key, self.course_run.key)

    @responses.activate
    def test_update_existing_program_type(self):

        fixture = json_serializer.Serializer().serialize([
            self.organization,
            self.seat_type_verified,
            self.program_type_masters,
            self.program,
        ])
        self._mock_fixture_response(fixture)
        self.reset_db_state()

        existing_program_type = self._set_up_masters_program_type()

        self._call_load_program_fixture([str(self.program.uuid)])

        stored_program = Program.objects.get(uuid=self.program.uuid)

        # assert existing DB value is used
        stored_program_type = stored_program.type
        self.assertEqual(stored_program_type, existing_program_type)

        # assert existing DB value is updated to match fixture
        stored_seat_types = list(stored_program_type.applicable_seat_types.all())
        self.assertEqual(len(stored_seat_types), 1)
        self.assertEqual(stored_seat_types[0].name, self.seat_type_verified.name)

    @responses.activate
    def test_remapping_courserun_programtype(self):
        """
        Tests whether the remapping of program types works for the course run field that points to them
        """
        self.course_run.expected_program_type = self.program_type_masters
        self.course_run.save()
        fixture = json_serializer.Serializer().serialize([
            self.program_type_masters,
            self.program_type_mm,
            self.organization,
            self.seat_type_verified,
            self.program,
            self.program_mm,
            self.curriculum_program_membership,
            self.curriculum_course_membership,
            self.curriculum,
            self.course,
            self.course_mm,
            self.course_run,
        ])
        self._mock_fixture_response(fixture)
        self.reset_db_state()

        existing_program_type = self._set_up_masters_program_type()

        self._call_load_program_fixture([str(self.program.uuid)])

        stored_courserun = CourseRun.objects.get(key=self.course_run.key)
        stored_program_type = stored_courserun.expected_program_type

        self.assertEqual(existing_program_type, stored_program_type)

    @responses.activate
    def test_existing_seat_types(self):

        fixture = json_serializer.Serializer().serialize([
            self.organization,
            self.seat_type_verified,
            self.program_type_masters,
            self.program,
        ])
        self._mock_fixture_response(fixture)
        self.reset_db_state()

        # create existing verified seat with different pk than fixture and
        # a second seat type with the same pk but different values
        new_pk = self.seat_type_verified.id + 1
        SeatType.objects.create(id=new_pk, name='Verified', slug='verified')
        SeatType.objects.create(id=self.seat_type_verified.id, name='Test', slug='test')
        self._call_load_program_fixture([str(self.program.uuid)])

        stored_program = Program.objects.get(uuid=self.program.uuid)
        stored_seat_type = stored_program.type.applicable_seat_types.first()

        self.assertEqual(stored_seat_type.id, new_pk)
        self.assertEqual(stored_seat_type.name, self.seat_type_verified.name)

    @responses.activate
    def test_fail_on_save_error(self):

        fixture = json_serializer.Serializer().serialize([
            self.organization,
        ])

        #  Should not be able to save an organization without uuid
        fixture_json = json.loads(fixture)
        fixture_json[0]['fields']['uuid'] = None
        fixture = json.dumps(fixture_json)

        self._mock_fixture_response(fixture)
        self.reset_db_state()

        with pytest.raises(IntegrityError) as err:
            self._call_load_program_fixture([str(self.program.uuid)])
        expected_msg = fr'Failed to save course_metadata.Organization\(pk={self.organization.id}\):'
        assert re.match(expected_msg, str(err.value))

    @responses.activate
    def test_fail_on_constraint_error(self):

        # duplicate programs should successfully save but fail final constraint check
        fixture = json_serializer.Serializer().serialize([
            self.program,
            self.program,
            self.seat_type_verified,
            self.program_type_masters,
        ])
        self._mock_fixture_response(fixture)
        self.reset_db_state()

        with pytest.raises(IntegrityError) as err:
            self._call_load_program_fixture([str(self.program.uuid)])
        expected_msg = (
            r'Checking database constraints failed trying to load fixtures. Unable to save program\(s\):'
        ).format(pk=self.organization.id)
        assert re.match(expected_msg, str(err.value))

    @responses.activate
    def test_ignore_program_external_key(self):
        fixture = json_serializer.Serializer().serialize([
            self.organization,
            self.seat_type_verified,
            self.program_type_masters,
            self.program,
        ])
        self._mock_fixture_response(fixture)
        self.reset_db_state()

        self._call_load_program_fixture([
            '{uuid}:{external_key}'.format(
                uuid=str(self.program.uuid),
                external_key='CS-104-FALL-2019'
            )
        ])

        Program.objects.get(uuid=self.program.uuid)

    @responses.activate
    def test_update_existing_data(self):

        fixture = json_serializer.Serializer().serialize([
            self.organization,
            self.seat_type_verified,
            self.program_type_masters,
            self.program,
            self.curriculum,
            self.course,
            self.course_run,
            self.curriculum_course_membership,
        ])
        self._mock_fixture_response(fixture)
        self._call_load_program_fixture([str(self.program.uuid)])

        self.program.title = 'program-title-modified'
        self.course.title = 'course-title-modified'
        new_course = CourseFactory(partner=self.partner, authoring_organizations=[self.organization])
        new_course_run = CourseRunFactory(course=new_course)
        new_course_membership = CurriculumCourseMembershipFactory(course=new_course, curriculum=self.curriculum)

        fixture = json_serializer.Serializer().serialize([
            self.organization,
            self.seat_type_verified,
            self.program_type_masters,
            self.program,
            self.curriculum,
            self.course,
            self.course_run,
            self.curriculum_course_membership,
            new_course_membership,
            new_course,
            new_course_run,
        ])
        responses.reset()
        self._mock_oauth_request()
        self._mock_fixture_response(fixture)
        self.reset_db_state()
        self._call_load_program_fixture([str(self.program.uuid)])

        stored_program = Program.objects.get(uuid=self.program.uuid)
        self.assertEqual(stored_program.title, 'program-title-modified')

        stored_program_courses = stored_program.curricula.first().course_curriculum.all()
        modified_existing_course = stored_program_courses.get(uuid=self.course.uuid)
        stored_new_course = stored_program_courses.get(uuid=new_course.uuid)

        self.assertEqual(len(stored_program_courses), 2)
        self.assertEqual(modified_existing_course.title, 'course-title-modified')
        self.assertEqual(stored_new_course.key, new_course.key)
