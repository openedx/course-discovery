import datetime

from django.conf import settings
from django.core.management import call_command
from django_elasticsearch_dsl.registries import registry
from freezegun import freeze_time

from course_discovery.apps.core.utils import ElasticsearchUtils


class TestRemoveUnusedIndexes:
    backend = None

    def test_handle(self, elasticsearch_dsl_default_connection):
        """ Verify the command removes all but the newest indexes. """

        # Use now as initial time, so indexes are created AFTER the current index so expected values are accurate
        initial_time = datetime.datetime.now()
        # Create 2 more indexes than we expect to exist after removal
        for number in range(1, settings.ELASTICSEARCH_DSL_INDEX_RETENTION_LIMIT + 2):
            current_time = initial_time + datetime.timedelta(seconds=number)
            freezer = freeze_time(current_time)
            freezer.start()
            for index in registry.get_indices():
                ElasticsearchUtils.create_index(index)
            freezer.stop()

        # Prune indexes and confirm the right indexes are removed
        call_command('remove_unused_indexes')
        indices_client = elasticsearch_dsl_default_connection.indices
        for index in registry.get_indices():
            # pylint:disable=protected-access
            current_alias = indices_client.get_alias(name=index._name[:-16])
            indexes_to_keep = current_alias.keys()

            # check that we keep the current indexes, which we don't want removed
            all_indexes = self.get_current_index_names(indices_client=indices_client, index_prefix=index._name[:-16])
            assert set(all_indexes).issuperset(set(indexes_to_keep))

            # check that other indexes are removed, excepting those that don't hit the retention limit
            expected_count = settings.ELASTICSEARCH_DSL_INDEX_RETENTION_LIMIT + len(indexes_to_keep)
            assert len(all_indexes) == expected_count

        # Attempt to prune indexes again and confirm that no indexes are removed
        call_command('remove_unused_indexes')

        for index in registry.get_indices():
            # check that we keep the current indexes, which we don't want removed
            # pylint:disable=protected-access
            all_indexes = self.get_current_index_names(indices_client=indices_client, index_prefix=index._name[:-16])
            current_alias = indices_client.get_alias(name=index._name[:-16])
            indexes_to_keep = current_alias.keys()
            assert set(all_indexes).issuperset(set(indexes_to_keep))

            # check that index count remains the same as before
            expected_count = settings.ELASTICSEARCH_DSL_INDEX_RETENTION_LIMIT + len(indexes_to_keep)
            assert len(all_indexes) == expected_count

        # Cleanup indexes created by this test
        for index in registry.get_indices():
            # pylint:disable=protected-access
            indices_client.delete(index=index._name + '_*')

    @staticmethod
    def get_current_index_names(indices_client, index_prefix):
        all_indexes = indices_client.get('*').keys()
        all_current_indexes = [index_name for index_name in all_indexes if index_name[:-16] == index_prefix]
        return all_current_indexes
