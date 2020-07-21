
from algoliasearch_django import AlgoliaIndex, register

from course_discovery.apps.course_metadata.algolia_models import (
    AlgoliaProxyCourse, AlgoliaProxyProduct, AlgoliaProxyProgram, SearchDefaultResultsConfiguration
)


class BaseProductIndex(AlgoliaIndex):
    language = None

    # Bit of a hack: Override get_queryset to return all wrapped versions of all courses and programs rather than an
    # actual queryset to get around the fact that courses and programs have different fields and therefore cannot be
    # combined in a union of querysets. AlgoliaIndex only uses get_queryset as an iterable, so an array works as well.

    def get_queryset(self):  # pragma: no cover
        if not self.language:
            raise Exception('Cannot update Algolia index \'{index_name}\'. No language set'.format(
                index_name=self.index_name))
        qs1 = [AlgoliaProxyProduct(course, self.language) for course in AlgoliaProxyCourse.objects.all()]
        qs2 = [AlgoliaProxyProduct(program, self.language) for program in AlgoliaProxyProgram.objects.all()]
        return qs1 + qs2

    def generate_empty_query_rule(self, rule_object_id, product_type, results):
        promoted_results = [{'objectID': '{type}-{uuid}'.format(type=product_type, uuid=result.uuid),
                             'position': index} for index, result in enumerate(results)]
        return {
            'objectID': rule_object_id,
            'condition': {
                'pattern': '',
                'anchoring': 'is',
                'alternatives': False
            },
            'consequence': {
                'promote': promoted_results,
                'filterPromotes': True
            }
        }

    def get_rules(self):
        rules_config = SearchDefaultResultsConfiguration.objects.filter(index_name=self.index_name).first()
        if rules_config:
            course_rule = self.generate_empty_query_rule('course-empty-query-rule', 'course',
                                                         rules_config.courses.all())
            program_rule = self.generate_empty_query_rule('program-empty-query-rule', 'program',
                                                          rules_config.programs.all())
            return [course_rule, program_rule]
        return []

    # Rules aren't automatically set in regular reindex_all, so set them explicitly
    def reindex_all(self, batch_size=1000):
        super().reindex_all(batch_size)
        self._AlgoliaIndex__index.replace_all_rules(self.get_rules())  # pylint: disable=no-member


class EnglishProductIndex(BaseProductIndex):
    language = 'en'

    search_fields = (('product_title', 'title'), ('partner_names', 'partner'), 'partner_keys',
                     'primary_description', 'secondary_description', 'tertiary_description')
    facet_fields = (('availability_level', 'availability'), ('subject_names', 'subject'), ('levels', 'level'),
                    ('active_languages', 'language'), ('product_type', 'product'), ('program_types', 'program_type'),
                    ('staff_slugs', 'staff'))
    ranking_fields = ('availability_rank', ('product_recent_enrollment_count', 'recent_enrollment_count'))
    result_fields = (('product_marketing_url', 'marketing_url'), ('product_card_image_url', 'card_image_url'),
                     ('product_uuid', 'uuid'), 'active_run_key', 'active_run_start', 'active_run_type', 'owners',
                     'course_titles')
    # Algolia needs this
    object_id_field = (('custom_object_id', 'objectID'), )
    fields = search_fields + facet_fields + ranking_fields + result_fields + object_id_field
    settings = {
        'searchableAttributes': [
            'unordered(title)',  # AG best practice: position of the search term in plain text fields doesn't matter
            'partner',
            'partner_keys',
            'unordered(primary_description)',
            'unordered(secondary_description)',
            'unordered(tertiary_description)',
        ],
        'attributesForFaceting': ['partner', 'availability', 'subject', 'level', 'language', 'product', 'program_type',
                                  'filterOnly(staff)'],
        'customRanking': ['asc(availability_rank)', 'desc(recent_enrollment_count)']
    }
    index_name = 'product'
    should_index = 'should_index'


class SpanishProductIndex(BaseProductIndex):
    language = 'es_419'

    search_fields = (('product_title', 'title'), ('partner_names', 'partner'), 'partner_keys',
                     'primary_description', 'secondary_description', 'tertiary_description')
    facet_fields = (('availability_level', 'availability'), ('subject_names', 'subject'), ('levels', 'level'),
                    ('active_languages', 'language'), ('product_type', 'product'), ('program_types', 'program_type'),
                    ('staff_slugs', 'staff'))
    ranking_fields = ('availability_rank', ('product_recent_enrollment_count', 'recent_enrollment_count'),
                      'promoted_in_spanish_index')
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
            'partner',
            'partner_keys',
            'unordered(primary_description)',
            'unordered(secondary_description)',
            'unordered(tertiary_description)',
        ],
        'attributesForFaceting': ['partner', 'availability', 'subject', 'level', 'language', 'product', 'program_type',
                                  'filterOnly(staff)'],
        'customRanking': ['desc(promoted_in_spanish_index)', 'asc(availability_rank)', 'desc(recent_enrollment_count)']
    }
    index_name = 'spanish_product'
    should_index = 'should_index'


# Standard algoliasearch_django pattern for populating 2 indices with one model. These are the signatures and structure
# AlgoliaIndex expects, so ignore warnings
# pylint: disable=no-member,super-init-not-called,dangerous-default-value
class ProductMetaIndex(AlgoliaIndex):
    model_index = []

    def __init__(self, model, client, settings):
        self.model_index = [
            EnglishProductIndex(model, client, settings),
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
