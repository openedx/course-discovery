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
    CourseRun, Curriculum, CurriculumCourseMembership, CurriculumProgramMembership
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

    Idempotent up to changes in the ids of records in the source
    environment; if a record previously copied by this command has
    been deleted in the source environment and then recreated under a
    new primary key then this command will likely fail.

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
            logger.info('Saved {object_label}(pk={pk})'.format(  # lint-amnesty, pylint: disable=logging-format-interpolation
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
        objects_to_be_loaded = []
        for item in deserialized_items:
            # partner models are not included in the fixture
            # replace partner with valid reference in this environment
            try:
                item.object._meta.get_field('partner')
                item.object.partner = partner
            except FieldDoesNotExist:
                pass

            objects_to_be_loaded.append(item)

        for obj in objects_to_be_loaded:
            self.save_fixture_object(obj)
