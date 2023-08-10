"""
Populate catalog programs for masters sandbox environment
"""
import logging
from contextlib import contextmanager
from posixpath import join as urljoin

from django import db
from django.core import serializers
from django.core.exceptions import FieldDoesNotExist
from django.core.management import BaseCommand, CommandError
from edx_rest_api_client import client as rest_client

from course_discovery.apps.core.models import Partner
from course_discovery.apps.course_metadata.models import (
    CourseRun, Curriculum, CurriculumCourseMembership, CurriculumProgramMembership, Program, ProgramType, SeatType
)
from course_discovery.apps.course_metadata.signals import (
    check_curriculum_for_cycles, check_curriculum_program_membership_for_cycles,
    ensure_external_key_uniqueness__course_run, ensure_external_key_uniqueness__curriculum,
    ensure_external_key_uniqueness__curriculum_course_membership
)

logger = logging.getLogger(__name__)


@contextmanager
def disconnect_program_signals():
    """
    Context manager to be used for temporarily disconnecting the following
    pre_save signals for verifying external course keys:
    - check_curriculum_for_cycles
    - check_curriculum_program_membership_for_cycles
    - ensure_external_key_uniqueness__course_run
    - ensure_external_key_uniqueness__curriculum
    - ensure_external_key_uniqueness__curriculum_course_membership
    """
    pre_save = db.models.signals.pre_save

    signals_list = [
        {
            'action': pre_save,
            'signal': check_curriculum_for_cycles,
            'sender': Curriculum,
        },
        {
            'action': pre_save,
            'signal': check_curriculum_program_membership_for_cycles,
            'sender': CurriculumProgramMembership,
        },
        {
            'action': pre_save,
            'signal': ensure_external_key_uniqueness__course_run,
            'sender': CourseRun,
        },
        {
            'action': pre_save,
            'signal': ensure_external_key_uniqueness__curriculum,
            'sender': Curriculum,
        },
        {
            'action': pre_save,
            'signal': ensure_external_key_uniqueness__curriculum_course_membership,
            'sender': CurriculumCourseMembership,
        },
    ]

    for signal in signals_list:
        signal['action'].disconnect(signal['signal'], sender=signal['sender'])

    try:
        yield
    finally:
        for signal in signals_list:
            signal['action'].connect(signal['signal'], sender=signal['sender'])


class Command(BaseCommand):
    """
    Command to populate catalog database with programs from another environment
    using the /program-fixtures endpoint

    Usage:
        ./manage.py load_program_fixture 707acbed-0dae-4e69-a629-1fa20b87ccf1:external_key
            --catalog-host http://edx.devstack.discovery:18381
            --oauth-host http://edx.devstack.lms:18000
            --client-id xxxxxxx --client-secret xxxxx
    """
    DEFAULT_PARTNER_CODE = 'edx'

    def add_arguments(self, parser):
        parser.add_argument('programs', help='comma separated list of program uuids or uuid:external_key mappings')
        parser.add_argument('--catalog-host', required=True)
        parser.add_argument('--oauth-host', required=True)
        parser.add_argument('--client-id', required=True)
        parser.add_argument('--client-secret', required=True)
        parser.add_argument('--partner-code', default=self.DEFAULT_PARTNER_CODE)

    def get_fixture(self, programs, catalog_host, auth_host, client_id, client_secret):
        client = rest_client.OAuthAPIClient(
            auth_host,
            client_id,
            client_secret,
        )

        url = urljoin(
            catalog_host,
            'extensions/api/v1/program-fixture/?programs={query}'.format(
                query=','.join(programs)
            )
        )

        response = client.request('GET', url)

        if response.status_code != 200:
            raise CommandError('Unexpected response loading programs from discovery service: {code} {msg}'.format(
                code=response.status_code,
                msg=response.text,
            ))

        return response.text

    def save_fixture_object(self, obj):
        try:
            obj.save()
            logger.info('Saved {object_label}(pk={pk})'.format(
                object_label=obj.object._meta.label,
                pk=obj.object.pk,
            ))
        except (db.DatabaseError, db.IntegrityError) as e:
            e.args = ('Failed to save {object_label}(pk={pk}): {error_msg}'.format(
                object_label=obj.object._meta.label,
                pk=obj.object.pk,
                error_msg=e,
            ),)
            raise

    def handle(self, *args, **options):
        programs = [program.split(':')[0] for program in options['programs'].split(',')]
        fixture = self.get_fixture(
            programs,
            options['catalog_host'],
            options['oauth_host'],
            options['client_id'],
            options['client_secret'],
        )

        partner = Partner.objects.get(short_code=options['partner_code'])

        connection = db.connections[db.DEFAULT_DB_ALIAS]

        with connection.constraint_checks_disabled():
            with disconnect_program_signals():
                self.load_fixture(fixture, partner)
        try:
            connection.check_constraints()
        except Exception as e:
            e.args = (
                "Checking database constraints failed trying to load fixtures. Unable to save program(s): %s" % e,
            )
            raise

    @db.transaction.atomic
    def load_fixture(self, fixture_text, partner):

        deserialized_items = serializers.deserialize('json', fixture_text)
        seat_type_map = {}
        program_type_map = {}
        objects_to_be_loaded = []
        for item in deserialized_items:
            # maps the pk of incoming SeatType/ProgramType references to a new
            # or existing model to avoid duplicate values.
            if isinstance(item.object, SeatType):
                stored_seat_type, created = SeatType.objects.get_or_create(name=item.object.name)
                seat_type_map[item.object.id] = (stored_seat_type, item)
            elif isinstance(item.object, ProgramType):
                # translated fields work differently in 'get' vs 'create', so need to explicitly call relation
                # in get and then set field in defaults
                stored_program_type, created = ProgramType.objects.get_or_create(translations__name_t=item.object.name,
                                                                                 defaults={'name_t': item.object.name})
                program_type_map[item.object.id] = (stored_program_type, item)
            else:
                # partner models are not included in the fixture
                # replace partner with valid reference in this environment
                try:
                    item.object._meta.get_field('partner')
                    item.object.partner = partner
                except FieldDoesNotExist:
                    pass

                objects_to_be_loaded.append(item)

        # set applicable_seat_types on each incoming program type to valid values
        # for this environment.  Remove any seat types not in the fixture data
        for stored_program_type, fixture_program_type in program_type_map.values():
            stored_program_type.applicable_seat_types.clear()
            for applicable_seat_type_id in fixture_program_type.m2m_data['applicable_seat_types']:
                try:
                    stored_program_type.applicable_seat_types.add(seat_type_map[applicable_seat_type_id][0])
                except KeyError:
                    msg = ('Failed to assign applicable_seat_type(pk={seat_type}) to ProgramType(pk={program_type}):'
                           'No matching SeatType in fixture')
                    logger.warning(msg.format(
                        seat_type=applicable_seat_type_id,
                        program_type=fixture_program_type.object.id,
                    ))
                    raise

        for obj in objects_to_be_loaded:
            # apply newly created/updated program_types to all programs
            # we're loading in
            if isinstance(obj.object, Program):
                try:
                    obj.object.type = program_type_map[obj.object.type_id][0]
                except KeyError:
                    msg = ('Failed to assign type(pk={program_type}) to Program(pk={program}):'
                           ' No matching ProgramType in fixture')
                    logger.warning(msg.format(
                        program_type=obj.object.type_id,
                        program=obj.object.id,
                    ))
                    raise
            elif isinstance(obj.object, CourseRun) and obj.object.expected_program_type_id:
                try:
                    obj.object.expected_program_type = program_type_map[obj.object.expected_program_type_id][0]
                except KeyError:
                    msg = ('Failed to assign program type (pk={program_type}) to CourseRun (pk={course_id}):'
                           ' No matching ProgramType in fixture')
                    logger.warning(msg.format(
                        program_type=obj.object.expected_program_type,
                        course_id=obj.object.key,
                    ))
                    raise

            self.save_fixture_object(obj)
