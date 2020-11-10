from elasticsearch_dsl import analyzer, token_filter

from course_discovery.settings.process_synonyms import get_synonym_lines_from_file

__all__ = ('html_strip', 'synonym_text', 'edge_ngram_completion', 'case_insensitive_keyword',)

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
        synonym_tokenfilter,
        # Note! 'snowball' comes after 'synonym_tokenfilter'
        'snowball',
    ],
    char_filter=['html_strip'],
)

edge_ngram_completion_filter = token_filter(
    'edge_ngram_completion_filter',
    type="edge_ngram",
    min_gram=2,
    max_gram=22
)


edge_ngram_completion = analyzer(
    "edge_ngram_completion",
    tokenizer="standard",
    filter=["lowercase", edge_ngram_completion_filter]
)

case_insensitive_keyword = analyzer(
    "case_insensitive_keyword",
    tokenizer="keyword",
    filter=["lowercase"]
)
