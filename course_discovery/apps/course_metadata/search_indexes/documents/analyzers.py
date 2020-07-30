from elasticsearch_dsl import analyzer, token_filter

from course_discovery.settings.process_synonyms import get_synonym_lines_from_file

__all__ = ('html_strip', 'synonym_text')

html_strip = analyzer(
    'html_strip', tokenizer='standard', filter=['lowercase', 'stop', 'snowball'], char_filter=['html_strip']
)

synonym_tokenfilter = token_filter('synonym_tokenfilter', 'synonym', synonyms=get_synonym_lines_from_file())

synonym_text = analyzer(
    'synonym_text',
    tokenizer='standard',
    filter=[
        # The ORDER is important here.
        'lowercase',
        'stop',
        synonym_tokenfilter,
        # Note! 'snowball' comes after 'synonym_tokenfilter'
        'snowball',
    ],
    char_filter=['html_strip'],
)
