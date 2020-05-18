
from algoliasearch_django import AlgoliaIndex, register

from course_discovery.apps.course_metadata.algolia_proxy_models import (
    AlgoliaProxyCourse, AlgoliaProxyProduct, AlgoliaProxyProgram
)

# TODO: make these configurable in Django Admin (WS-1025)
PINNED_COURSE_UUIDS = [
    '0e575a39-da1e-4e33-bb3b-e96cc6ffc58e',
    '911175d0-6724-4276-a058-c7b052773dd1',
    'da1b2400-322b-459b-97b0-0c557f05d017',
    'ff1df27b-3c97-42ee-a9b3-e031ffd41a4f',
    'a00ec61d-e2db-45c8-92c9-4727056c2f4a',
    '605e56d5-08f3-4e90-b4be-2c303def0cd5',
    '327c8e4f-315a-417b-9857-046dfc90c243',
    '0cdd5dc6-a20e-4d34-a346-fcbb9c4249f8',
    'bc4d1642-8b96-44b0-82e8-be8be6e44f94',
    '81cfc304-0eed-4779-9de8-41c79504e456',
    '97f16f83-5e8a-496c-9086-5634c8edccbb',
    'f692cd0b-a77a-4fdf-87db-a309677633e6',
    '15923a19-7f31-4767-a7a0-73da8886f7b8',
    '6e418821-0e4c-4b16-94a3-18979ee49717',
    'c6ad9bb7-cafc-48c8-92e5-5f0900460e66',
    'ec5e106e-18be-4bf3-8721-58950b7da1d4',
    '91f52ef3-fa3f-4934-9d19-8d5a32635cd4',
    '381a0046-5d78-4790-8776-74620d59f48e',
    '8a140470-bc70-4f7f-a9aa-df0284469b0b',
    '459e3763-8724-4f36-9e99-387d55b0dbf5']


PINNED_PROGRAM_UUIDS = [
    '3178ea5b-b7a1-4439-a8b5-aad5df14af34',
    'a3951294-926b-4247-8c3c-51c1e4347a15',
    '3c32e3e0-b6fe-4ee4-bd4f-210c6339e074',
    '9b729425-b524-4344-baaa-107abdee62c6'
]


def get_promoted_courses():
    return [{'objectID': 'course-{uuid}'.format(uuid=uuid), 'position': index} for
            index, uuid in enumerate(PINNED_COURSE_UUIDS)]


def get_promoted_programs():
    return [{'objectID': 'program-{uuid}'.format(uuid=uuid), 'position': index} for
            index, uuid in enumerate(PINNED_PROGRAM_UUIDS)]


class ProductIndex(AlgoliaIndex):
    # promote specified course/program results when query is empty (eg in pre-search state)
    rules = [
        {
            'objectID': 'empty-query-rule-courses',
            'condition': {
                'pattern': '',
                'anchoring': 'is',
                'alternatives': False
            },
            'consequence': {
                'promote': get_promoted_courses(),
                'filterPromotes': True
            },
        },
        {
            'objectID': 'empty-query-rule-programs',
            'condition': {
                'pattern': '',
                'anchoring': 'is',
                'alternatives': False
            },
            'consequence': {
                'promote': get_promoted_programs(),
                'filterPromotes': True
            }
        }
    ]
    search_fields = (('partner_names', 'partner'), ('product_title', 'title'), 'primary_description',
                     'secondary_description', 'tertiary_description')
    facet_fields = (('availability_level', 'availability'), ('subject_names', 'subject'), ('levels', 'level'),
                    ('active_languages', 'language'), ('product_type', 'product'), ('program_types', 'program_type'))
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
            'unordered(primary_description)',
            'unordered(secondary_description)',
            'unordered(tertiary_description)',
            'partner'
        ],
        'attributesForFaceting': ['partner', 'availability', 'subject', 'level', 'language', 'product', 'program_type'],
        'customRanking': ['asc(availability_rank)', 'desc(recent_enrollment_count)']
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

    # Rules aren't automatically set in regular reindex_all, so set them explicitly
    def reindex_all(self, batch_size=1000):
        super().reindex_all(batch_size)
        self._AlgoliaIndex__index.replace_all_rules(self.rules)  # pylint: disable=no-member


class SpanishProductIndex(AlgoliaIndex):
    search_fields = (('partner_names', 'partner'), ('product_title', 'title'), 'primary_description',
                     'secondary_description', 'tertiary_description')
    facet_fields = (('availability_level', 'availability'), ('subject_names', 'subject'), ('levels', 'level'),
                    ('active_languages', 'language'), ('product_type', 'product'), ('program_types', 'program_type'))
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
            'unordered(primary_description)',
            'unordered(secondary_description)',
            'unordered(tertiary_description)',
            'partner'
        ],
        'attributesForFaceting': ['partner', 'availability', 'subject', 'level', 'language', 'product', 'program_type'],
        'customRanking': ['desc(promoted_in_spanish_index)', 'asc(availability_rank)', 'desc(recent_enrollment_count)']
    }
    index_name = 'spanish_product'
    should_index = 'should_index'

    def get_queryset(self):  # pragma: no cover
        qs1 = [AlgoliaProxyProduct(course, 'es_419') for course in AlgoliaProxyCourse.objects.all()]
        qs2 = [AlgoliaProxyProduct(program, 'es_419') for program in AlgoliaProxyProgram.objects.all()]
        return qs1 + qs2


# Standard algoliasearch_django pattern for populating 2 indices with one model. These are the signatures and structure
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
