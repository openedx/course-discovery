from algoliasearch_django import AlgoliaIndex, register

from course_discovery.apps.course_metadata.algolia_models import (
    AlgoliaProxyCourse, AlgoliaProxyProduct, AlgoliaProxyProgram, SearchDefaultResultsConfiguration
)
from course_discovery.apps.course_metadata.contentful_utils import (
    fetch_and_transform_bootcamp_contentful_data, fetch_and_transform_degree_contentful_data
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

        bootcamp_contentful_data = fetch_and_transform_bootcamp_contentful_data()
        qs1 = [AlgoliaProxyProduct(course, self.language, contentful_data=bootcamp_contentful_data)
               for course in AlgoliaProxyCourse.objects.all()]

        degree_contentful_data = fetch_and_transform_degree_contentful_data()
        qs2 = [AlgoliaProxyProduct(program, self.language, contentful_data=degree_contentful_data)
               for program in AlgoliaProxyProgram.objects.all()]

        return qs1 + qs2

    def generate_empty_query_rule(self, rule_object_id, product_type, results):
        promoted_results = [{'objectID': f'{product_type}-{result.uuid}',
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
        # Since reindexing removes all the rules, we will need to recreate the 2U rules after reindexing
        rules_to_create = self.get_rules()
        rules_to_create_ids = {rule['objectID'] for rule in rules_to_create}
        existing_rules_to_keep = [
            rule for rule in self._AlgoliaIndex__index.iter_rules()
            if rule['objectID'] not in rules_to_create_ids
        ]
        final_rules = rules_to_create + existing_rules_to_keep
        super().reindex_all(batch_size)
        self._AlgoliaIndex__index.replace_all_rules(final_rules)


class EnglishProductIndex(BaseProductIndex):
    language = 'en'

    search_fields = (('product_title', 'title'), ('partner_names', 'partner'), 'partner_keys',
                     'primary_description', 'secondary_description', 'tertiary_description', 'tags')
    facet_fields = (('availability_level', 'availability'), ('subject_names', 'subject'), ('levels', 'level'),
                    ('active_languages', 'language'), ('product_type', 'product'), ('program_types', 'program_type'),
                    ('staff_slugs', 'staff'), ('product_allowed_in', 'allowed_in'),
                    ('product_blocked_in', 'blocked_in'))
    ranking_fields = ('availability_rank', ('product_recent_enrollment_count', 'recent_enrollment_count'),
                      ('product_value_per_click_usa', 'value_per_click_usa'),
                      ('product_value_per_click_international', 'value_per_click_international'),
                      ('product_value_per_lead_usa', 'value_per_lead_usa'),
                      ('product_value_per_lead_international', 'value_per_lead_international'))
    result_fields = (('product_marketing_url', 'marketing_url'), ('product_card_image_url', 'card_image_url'),
                     ('product_uuid', 'uuid'), ('product_weeks_to_complete', 'weeks_to_complete'),
                     ('product_max_effort', 'max_effort'), ('product_min_effort', 'min_effort'),
                     ('product_organization_short_code_override', 'organization_short_code_override'),
                     ('product_organization_logo_override', 'organization_logo_override'),
                     ('product_meta_title', 'meta_title'),
                     'active_run_key', 'active_run_start', 'active_run_type', 'owners', 'course_titles', 'tags',
                     'skills', 'contentful_fields',)

    # Algolia needs this
    object_id_field = (('custom_object_id', 'objectID'), )
    fields = search_fields + facet_fields + ranking_fields + result_fields + object_id_field
    geo_field = 'coordinates'
    settings = {
        'searchableAttributes': [
            'unordered(title)',  # AG best practice: position of the search term in plain text fields doesn't matter
            'partner',
            'partner_keys',
            'unordered(primary_description)',
            'unordered(secondary_description)',
            'unordered(tertiary_description)',
            'tags',
            'contentful_fields.page_title, contentful_fields.subheading, contentful_fields.about_the_program, '
            'contentful_fields.faq_items, contentful_fields.featured_products'
        ],
        'attributesForFaceting': [
            'partner', 'availability', 'subject', 'level', 'language', 'product', 'program_type',
            'filterOnly(staff)', 'filterOnly(allowed_in)', 'filterOnly(blocked_in)', 'skills.skill',
            'skills.category', 'skills.subcategory', 'tags',
        ],
        'customRanking': ['asc(availability_rank)', 'desc(recent_enrollment_count)']
    }
    index_name = 'product'
    should_index = 'should_index'


class SpanishProductIndex(BaseProductIndex):
    language = 'es_419'

    search_fields = (('product_title', 'title'), ('partner_names', 'partner'), 'partner_keys',
                     'primary_description', 'secondary_description', 'tertiary_description', 'tags')
    facet_fields = (('availability_level', 'availability'), ('subject_names', 'subject'), ('levels', 'level'),
                    ('active_languages', 'language'), ('product_type', 'product'), ('program_types', 'program_type'),
                    ('staff_slugs', 'staff'), ('product_allowed_in', 'allowed_in'),
                    ('product_blocked_in', 'blocked_in'))
    ranking_fields = ('availability_rank', ('product_recent_enrollment_count', 'recent_enrollment_count'),
                      ('product_value_per_click_usa', 'value_per_click_usa'),
                      ('product_value_per_click_international', 'value_per_click_international'),
                      ('product_value_per_lead_usa', 'value_per_lead_usa'),
                      ('product_value_per_lead_international', 'value_per_lead_international'),
                      'promoted_in_spanish_index')
    result_fields = (('product_marketing_url', 'marketing_url'), ('product_card_image_url', 'card_image_url'),
                     ('product_uuid', 'uuid'), ('product_weeks_to_complete', 'weeks_to_complete'),
                     ('product_max_effort', 'max_effort'), ('product_min_effort', 'min_effort'), 'active_run_key',
                     ('product_organization_short_code_override', 'organization_short_code_override'),
                     ('product_organization_logo_override', 'organization_logo_override'),
                     ('product_meta_title', 'meta_title'), 'active_run_start', 'active_run_type',
                     'owners', 'course_titles', 'tags', 'skills', 'contentful_fields',)

    # Algolia uses objectID as unique identifier. Can't use straight uuids because a program and a course could
    # have the same one, so we add 'course' or 'program' as a prefix
    object_id_field = (('custom_object_id', 'objectID'), )
    fields = search_fields + facet_fields + ranking_fields + result_fields + object_id_field
    geo_field = 'coordinates'
    settings = {
        'searchableAttributes': [
            'unordered(title)',  # Algolia best practice: position of the term in plain text fields doesn't matter
            'partner',
            'partner_keys',
            'unordered(primary_description)',
            'unordered(secondary_description)',
            'unordered(tertiary_description)',
            'tags',
            'contentful_fields.page_title, contentful_fields.subheading, contentful_fields.about_the_program, '
            'contentful_fields.faq_items, contentful_fields.featured_products'
        ],
        'attributesForFaceting': [
            'partner', 'availability', 'subject', 'level', 'language', 'product', 'program_type',
            'filterOnly(staff)', 'filterOnly(allowed_in)', 'filterOnly(blocked_in)',
            'skills.skill', 'skills.category', 'skills.subcategory', 'tags'
        ],
        'customRanking': ['desc(promoted_in_spanish_index)', 'asc(availability_rank)', 'desc(recent_enrollment_count)']
    }
    index_name = 'spanish_product'
    should_index = 'should_index_spanish'


# Standard algoliasearch_django pattern for populating 2 indices with one model. These are the signatures and structure
# AlgoliaIndex expects, so ignore warnings
# pylint: disable=super-init-not-called,dangerous-default-value
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
