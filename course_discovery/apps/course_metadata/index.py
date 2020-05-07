
from algoliasearch_django import AlgoliaIndex, register

from course_discovery.apps.course_metadata.algolia_proxy_models import (
    AlgoliaProxyCourse, AlgoliaProxyProduct, AlgoliaProxyProgram
)


class ProductIndex(AlgoliaIndex):
    search_fields = (('partner_names', 'partner'), ('product_title', 'title'), 'primary_description',
                     'secondary_description', 'tertiary_description')
    facet_fields = (('availability_level', 'availability'), ('subject_names', 'subject'), ('levels', 'level'),
                    ('active_languages', 'language'), ('product_type', 'product'), ('program_types', 'program_type'))
    ranking_fields = ('availability_rank', ('product_recent_enrollment_count', 'recent_enrollment_count'),
                      # TEMPORARY: Demote Professional Certificate programs until promoted programs are in place
                      'is_prof_cert_program')
    result_fields = (('product_marketing_url', 'marketing_url'), ('product_card_image_url', 'card_image_url'),
                     ('product_uuid', 'uuid'), 'active_run_key', 'active_run_start', 'active_run_type', 'owners',
                     'course_titles')
    # Algolia needs this
    object_id_field = (('custom_object_id', 'objectID'), )
    fields = search_fields + facet_fields + ranking_fields + result_fields + object_id_field
    settings = {
        'searchableAttributes': [
            'unordered(title)',  # AG best practice: position of the search term in plain text fields doesn't matter
            'unordered(primary_description)',
            'unordered(secondary_description)',
            'unordered(tertiary_description)',
            'partner'
        ],
        'attributesForFaceting': ['partner', 'availability', 'subject', 'level', 'language', 'product', 'program_type'],
        'customRanking': ['asc(availability_rank)', 'asc(is_prof_cert_program)', 'desc(recent_enrollment_count)']
    }
    index_name = 'product'
    should_index = 'should_index'

    # Bit of a hack: Override get_queryset to return all wrapped versions of all courses and programs rather than an
    # actual queryset to get around the fact that courses and programs have different fields and therefore cannot be
    # combined in a union of querysets. AlgoliaIndex only uses get_queryset as an iterable, so an array works as well.
    def get_queryset(self):  # pragma: no cover
        qs1 = [AlgoliaProxyProduct(course) for course in AlgoliaProxyCourse.objects.all()]
        qs2 = [AlgoliaProxyProduct(program) for program in AlgoliaProxyProgram.objects.all()]
        return qs1 + qs2


class SpanishProductIndex(AlgoliaIndex):
    search_fields = (('partner_names', 'partner'), ('product_title', 'title'), 'primary_description',
                     'secondary_description', 'tertiary_description')
    facet_fields = (('availability_level', 'availability'), ('subject_names', 'subject'), ('levels', 'level'),
                    ('active_languages', 'language'), ('product_type', 'product'), ('program_types', 'program_type'))
    ranking_fields = ('availability_rank', ('product_recent_enrollment_count', 'recent_enrollment_count'),
                      # TEMPORARY: Demote Professional Certificate programs until promoted programs are in place
                      'is_prof_cert_program')
    result_fields = (('product_marketing_url', 'marketing_url'), ('product_card_image_url', 'card_image_url'),
                     ('product_uuid', 'uuid'), 'active_run_key', 'active_run_start', 'active_run_type', 'owners',
                     'course_titles')
    # Algolia uses objectID as unique identifier. Can't use straight uuids because a program and a course could
    # have the same one, so we add 'course' or 'program' as a prefix
    object_id_field = (('custom_object_id', 'objectID'), )
    fields = search_fields + facet_fields + ranking_fields + result_fields + object_id_field
    settings = {
        'searchableAttributes': [
            'unordered(title)',  # Algolia best practice: position of the term in plain text fields doesn't matter
            'unordered(primary_description)',
            'unordered(secondary_description)',
            'unordered(tertiary_description)',
            'partner'
        ],
        'attributesForFaceting': ['partner', 'availability', 'subject', 'level', 'language', 'product', 'program_type'],
        'customRanking': ['asc(availability_rank)', 'asc(is_prof_cert_program)', 'desc(recent_enrollment_count)']
    }
    index_name = 'spanish_product'
    should_index = 'should_index'

    def get_queryset(self):  # pragma: no cover
        qs1 = [AlgoliaProxyProduct(course, 'es_419') for course in AlgoliaProxyCourse.objects.all()]
        qs2 = [AlgoliaProxyProduct(program, 'es_419') for program in AlgoliaProxyProgram.objects.all()]
        return qs1 + qs2


# Standard algoliadjango pattern for populating 2 indices with one model. These are the signatures and structure
# AlgoliaIndex expects, so ignore warnings
# pylint: disable=no-member,super-init-not-called,dangerous-default-value
class ProductMetaIndex(AlgoliaIndex):
    model_index = []

    def __init__(self, model, client, settings):
        self.model_index = [
            ProductIndex(model, client, settings),
            SpanishProductIndex(model, client, settings),
        ]

    def update_obj_index(self, instance):
        for indexer in self.model_index:
            indexer.update_obj_index(instance)

    def delete_obj_index(self, instance):
        for indexer in self.model_index:
            indexer.delete_obj_index(instance)

    def raw_search(self, query='', params={}):
        res = {}
        for indexer in self.model_index:
            res[indexer.name] = indexer.raw_search(query, params)
        return res

    def set_settings(self):
        for indexer in self.model_index:
            indexer.set_settings()

    def clear_index(self):
        for indexer in self.model_index:
            indexer.clear_index()

    def reindex_all(self, batch_size=1000):
        for indexer in self.model_index:
            indexer.reindex_all(batch_size)


register(AlgoliaProxyProduct, index_cls=ProductMetaIndex)
