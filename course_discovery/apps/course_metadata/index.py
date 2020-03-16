
from algoliasearch_django import AlgoliaIndex
from algoliasearch_django.decorators import register

from course_discovery.apps.course_metadata.algolia_proxy_models import AlgoliaProxyCourse, AlgoliaProxyProgram


@register(AlgoliaProxyCourse)
class CourseIndex(AlgoliaIndex):
    search_fields = ('full_description', 'outcome', ('partner_names', 'partner'), 'short_description', 'title',)
    # partner is also a facet field, but we already declared it above
    facet_fields = ('availability', ('subject_names', 'subjects'), ('level_type_name', 'level'),
                    ('active_run_language', 'language'),)
    result_fields = ('active_run_key', 'active_run_start', 'active_run_type', 'active_url_slug', 'image_src', 'owners',
                     'program_types', ('uuid', 'objectID'), 'availability_rank', 'recent_enrollment_count')
    fields = search_fields + facet_fields + result_fields
    settings = {
        # searchableAttributes ordered by highest value
        'searchableAttributes': [
            'unordered(title)',  # AG best practice: position of the search term within the title doesn't matter
            'short_description',
            'full_description',
            'outcome',
            'partner'
        ],
        'attributesForFaceting': ['partner', 'subject', 'level', 'language', 'availability'],
        'customRanking': ['asc(availability_rank)', 'desc(recent_enrollment_count)']
    }
    index_name = 'course'
    should_index = 'should_index'


@register(AlgoliaProxyProgram)
class ProgramIndex(AlgoliaIndex):
    search_fields = (('partner_names', 'partner'), 'title', 'subtitle', 'overview',
                     ('expected_learning_items_values', 'expected_learning_items'))
    facet_fields = (('status', 'availability'), ('subject_names', 'subjects'), ('levels', 'level'),
                    ('active_languages', 'language'), 'card_image_url')
    result_fields = ('course_titles', 'marketing_url', 'program_type', 'owners', ('uuid', 'objectID'))
    fields = search_fields + facet_fields + result_fields
    settings = {
        'searchableAttributes': [
            'unordered(title)',  # AG best practice: position of the search term within the title doesn't matter
            'unordered(subtitle)',
            'overview',
            'expected_learning_items_values',
            'partner'
        ],
        'attributesForFaceting': ['partner', 'subject', 'level', 'language', 'availability']}
    index_name = 'program'
    should_index = 'should_index'
