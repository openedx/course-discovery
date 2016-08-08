RESERVED_ELASTICSEARCH_QUERY_OPERATORS = ('AND', 'OR', 'NOT', 'TO',)


def clean_query(query):
    """ Prepares a raw query for search.

    Args:
        query (str): query to clean.

    Returns:
        str: cleaned query
    """
    # Ensure the query is lowercase, since that is how we index our data.
    query = query.lower()

    # Specifying a SearchQuerySet filter will append an explicit AND clause to the query, thus changing its semantics.
    # So we wrap parentheses around the original query in order to preserve the semantics.
    query = '({qs})'.format(qs=query)

    # Ensure all operators are uppercase
    for operator in RESERVED_ELASTICSEARCH_QUERY_OPERATORS:
        old = ' {0} '.format(operator.lower())
        new = ' {0} '.format(operator.upper())
        query = query.replace(old, new)

    return query
