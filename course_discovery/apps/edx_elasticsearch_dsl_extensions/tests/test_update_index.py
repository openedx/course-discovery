import mock
import pytest
from django.conf import settings
from django.core.management import CommandError, call_command
from django.test import TestCase, override_settings
from freezegun import freeze_time

from course_discovery.apps.core.tests.mixins import ElasticsearchTestMixin
from course_discovery.apps.course_metadata.tests.factories import CourseRunFactory, PersonFactory, ProgramFactory
from course_discovery.apps.edx_elasticsearch_dsl_extensions.tests.mixins import SearchIndexTestMixin


@override_settings(ELASTICSEARCH_DSL_SIGNAL_PROCESSOR='django_elasticsearch_dsl.signals.BaseSignalProcessor')
class UpdateIndexTests(ElasticsearchTestMixin, SearchIndexTestMixin, TestCase):
    @freeze_time('2016-06-21')
    def test_handle(self):
        """ Verify the command creates a timestamped index and repoints the alias. """
        with mock.patch('course_discovery.apps.edx_elasticsearch_dsl_extensions.management.commands.'
                        'search_index.Command.sanity_check_new_index', return_value=(True, '')):
            call_command('search_index', '--update')

        for alias in settings.ELASTICSEARCH_INDEX_NAMES.values():
            index = '{alias}_20160621_000000'.format(alias=alias)
            response = self.conn.indices.get_alias(name=alias)
            expected = {
                index: {
                    'aliases': {
                        alias: {}
                    }
                }
            }
            self.assertDictEqual(response, expected)

    def test_sanity_check_error(self):
        """ Verify the command raises a CommandError if new index fails the sanity check. """
        CourseRunFactory()
        record_count = 2
        additional_runs = int(100 * settings.INDEX_SIZE_CHANGE_THRESHOLD + 1)
        CourseRunFactory.create_batch(additional_runs)

        # Ensure that an error is raised if the sanity check does not pass
        with pytest.raises(CommandError):
            with mock.patch('course_discovery.apps.edx_elasticsearch_dsl_extensions.management.commands.'
                            'search_index.Command.set_alias', return_value=True):
                with mock.patch('course_discovery.apps.edx_elasticsearch_dsl_extensions.management.commands.'
                                'search_index.Command.get_record_count', return_value=record_count):
                    call_command('search_index', '--update')

    def test_sanity_check_success(self):
        """ Verify the command does not raise a CommandError error if the new index passes the sanity check. """
        CourseRunFactory.create_batch(59)
        ProgramFactory.create_batch(59)
        PersonFactory.create_batch(59)
        record_count = 60

        # Ensure that no error is raised and the sanity check passes the second time
        with mock.patch('course_discovery.apps.edx_elasticsearch_dsl_extensions.management.commands.'
                        'search_index.Command.set_alias', return_value=True):
            with mock.patch('course_discovery.apps.edx_elasticsearch_dsl_extensions.management.commands.'
                            'search_index.Command.get_record_count', return_value=record_count):
                call_command('search_index', '--update')

    @freeze_time('2016-06-21')
    def test_sanity_check_disabled(self):
        """ Verify the sanity check can be disabled. """
        with mock.patch('course_discovery.apps.edx_elasticsearch_dsl_extensions.management.commands.'
                        'search_index.Command.sanity_check_new_index') as mock_sanity_check_new_index:
            call_command('search_index', '--update', disable_change_limit=True)
            self.assertFalse(mock_sanity_check_new_index.called)
