import importlib
from functools import lru_cache

from django.conf import settings


def process_synonyms(es, synonyms):
    """Convert synonyms to analyzed form with snowball analyzer.

    This method takes list of synonyms in the form 'running, jogging',
    applies the snowball analyzer and returns a list of synonyms in the format 'run, jog'.

    Attributes:
        es (client): client for making requests to es
        synonyms (list): list of synonyms (each synonym group is a comma separated string)
    """

    processed_synonyms = []
    for line in synonyms:
        processed_line = []
        for synonym in line:
            response = es.indices.analyze(text=synonym, analyzer='snowball')
            synonym_tokens = ' '.join([item['token'] for item in response['tokens']])
            processed_line.append(synonym_tokens)
        processed_line = ','.join(processed_line)
        processed_synonyms.append(processed_line)
    return processed_synonyms


def get_synonym_lines_from_file():
    synonyms_module = importlib.import_module(settings.SYNONYMS_MODULE)
    return synonyms_module.SYNONYMS


@lru_cache
def get_synonyms(es):
    synonyms = get_synonym_lines_from_file()
    synonyms = process_synonyms(es, synonyms)
    return synonyms
