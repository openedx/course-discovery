
from algoliasearch_django import AlgoliaIndex
from algoliasearch_django.decorators import register

from course_discovery.apps.course_metadata.algolia_proxy_models import AlgoliaProxyCourse, AlgoliaProxyProgram


@register(AlgoliaProxyCourse)
class CourseIndex(AlgoliaIndex):
    search_fields = ('full_description', 'outcome', ('partner_name', 'partner'), 'short_description', 'title',)
    # partner is also a facet field, but we already declared it above
    facet_fields = ('availability', ('subject_names', 'subjects'), ('level_type_name', 'level'),
                    ('active_run_language', 'language'),)
    result_fields = ('active_run_key', 'active_run_start', 'active_run_type', 'active_url_slug', 'image_src', 'owners',
                     'program_types', ('uuid', 'objectID'))
    fields = search_fields + facet_fields + result_fields
    settings = {
        # searchableAttributes ordered by highest value
        'searchableAttributes': ['title', 'short_description', 'full_description', 'outcome', 'partner'],
        'attributesForFaceting': ['partner', 'subject', 'level', 'language', 'availability']}
    index_name = 'course'


@register(AlgoliaProxyProgram)
class ProgramIndex(AlgoliaIndex):
    search_fields = (('partner_name', 'partner'), 'title', 'subtitle', 'overview',
                     ('expected_learning_items_values', 'expected_learning_items'))
    facet_fields = (('status', 'availability'), ('subject_names', 'subjects'), ('levels', 'level'),
                    ('active_languages', 'language'), 'card_image_url')
    result_fields = ('course_titles', 'marketing_url', 'program_type', 'owners', ('uuid', 'objectID'))
    fields = search_fields + facet_fields + result_fields
    settings = {'searchableAttributes': ['title', 'subtitle', 'overview', 'expected_learning_items_values', 'partner'],
                'attributesForFaceting': ['partner', 'subject', 'level', 'language', 'availability']}
    index_name = 'program'
