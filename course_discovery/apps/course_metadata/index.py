
from algoliasearch_django import AlgoliaIndex
from algoliasearch_django.decorators import register

from course_discovery.apps.course_metadata.algolia_proxy_models import (
    AlgoliaProxyCourse, AlgoliaProxyProduct, AlgoliaProxyProgram
)


@register(AlgoliaProxyProduct)
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
    # combined in a union of querysets.
    def get_queryset(self):  # pragma: no cover
        qs1 = [AlgoliaProxyProduct(course) for course in AlgoliaProxyCourse.objects.all()]
        qs2 = [AlgoliaProxyProduct(program) for program in AlgoliaProxyProgram.objects.all()]
        return qs1 + qs2
