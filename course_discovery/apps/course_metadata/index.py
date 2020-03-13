
from algoliasearch_django import AlgoliaIndex
from algoliasearch_django.decorators import register
from django.db.models import Value, CharField

from course_discovery.apps.course_metadata.algolia_proxy_models import AlgoliaProxyCourse, AlgoliaProxyProgram

'''
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
'''

'''
@register(AlgoliaProxyProgram)
class ProgramIndex(AlgoliaIndex):

    should_index = 'should_index'
'''

@register(AlgoliaProxyProgram)
class ProductIndex(AlgoliaIndex):
    search_fields = (('partner_names', 'partner'), 'title', 'primary_description', 'secondary_description',
                     'tertiary_description')
    facet_fields = (('availability_level','availability'), ('subject_names', 'subjects'), ('levels', 'level'),
                    ('active_languages', 'language'), ('product_type', 'product'))
    ranking_fields = ('availability_rank', 'recent_enrollment_count')
    result_fields = ('marketing_url', 'card_image_url', 'objectID', 'uuid', 'active_run_key', 'active_run_start',
                     'active_run_type', 'owners', 'program_types')
    fields = search_fields + facet_fields + ranking_fields + result_fields
    settings = {
        'searchableAttributes': [
            'unordered(title)',  # AG best practice: position of the search term within the title doesn't matter
            'primary_description',
            'secondary_description',
            'tertiary_description',
            'partner'
        ],
        'attributesForFaceting': ['partner', 'subject', 'level', 'language', 'availability', 'product'],
        'customRanking': ['asc(availability_rank)', 'desc(recent_enrollment_count)']
    }
    index_name = 'product'
    should_index = 'should_index'

    def get_queryset(self):
        qs1 = AlgoliaProxyCourse.objects.all().values('id','uuid').annotate(type=Value('course',CharField()))
        qs2 = AlgoliaProxyProgram.objects.all().values('id','uuid').annotate(type=Value('pgm',CharField()))
        return qs1.union(qs2)

    def get_raw_record(self, instance):
        if instance['type'] == "pgm":
            return super().get_raw_record(AlgoliaProxyProgram.objects.get(id=instance['id']))
        return super().get_raw_record(AlgoliaProxyCourse.objects.get(id=instance['id']))