import datetime

from django.conf import settings
from django.core.management import call_command
from freezegun import freeze_time

from course_discovery.apps.core.utils import ElasticsearchUtils


class TestRemoveUnusedIndexes:
    backend = None

    def test_handle(self, haystack_default_connection):
        """ Verify the command removes all but the newest indexes. """
        backend = haystack_default_connection

        # Use now as initial time, so indexes are created AFTER the current index so expected values are accurate
        initial_time = datetime.datetime.now()

        # Create 2 more indexes than we expect to exist after removal
        for number in range(1, settings.HAYSTACK_INDEX_RETENTION_LIMIT + 2):
            current_time = initial_time + datetime.timedelta(seconds=number)
            freezer = freeze_time(current_time)
            freezer.start()
            ElasticsearchUtils.create_index(es_connection=backend.conn, prefix=backend.index_name)
            freezer.stop()

        # Prune indexes and confirm the right indexes are removed
        call_command('remove_unused_indexes')
        current_alias_name = backend.index_name
        indices_client = backend.conn.indices
        current_alias = indices_client.get_alias(name=current_alias_name)
        indexes_to_keep = current_alias.keys()

        # check that we keep the current indexes, which we don't want removed
        all_indexes = self.get_current_index_names(indices_client=indices_client, index_prefix=backend.index_name)
        assert set(all_indexes).issuperset(set(indexes_to_keep))

        # check that other indexes are removed, excepting those that don't hit the retention limit
        expected_count = settings.HAYSTACK_INDEX_RETENTION_LIMIT + len(indexes_to_keep)
        assert len(all_indexes) == expected_count

        # Attempt to prune indexes again and confirm that no indexes are removed
        call_command('remove_unused_indexes')

        # check that we keep the current indexes, which we don't want removed
        all_indexes = self.get_current_index_names(indices_client=indices_client, index_prefix=backend.index_name)
        assert set(all_indexes).issuperset(set(indexes_to_keep))

        # check that index count remains the same as before
        assert len(all_indexes) == expected_count

        # Cleanup indexes created by this test
        backend.conn.indices.delete(index=backend.index_name + '_*')

    @staticmethod
    def get_current_index_names(indices_client, index_prefix):
        all_index_settings = indices_client.get_settings()
        all_indexes = list(all_index_settings.keys())
        all_current_indexes = [index_name for index_name in all_indexes if index_name.startswith(index_prefix + '_')]
        return all_current_indexes
