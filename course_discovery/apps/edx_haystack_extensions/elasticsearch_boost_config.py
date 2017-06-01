# pylint: disable=line-too-long
def get_elasticsearch_boost_config():
    """
    Custom boosting config used to control relevance scores.

    For a good primer on the theory behind relevance scoring, read
    https://www.elastic.co/guide/en/elasticsearch/guide/1.x/scoring-theory.html.

    If you're trying to tweak this config locally with a small dataset and are
    seeing strange relevance scores, keep in mind that Elasticsearch computes
    shard-local relevance scores. This causes small discrepancies between relevance
    scores across shards that become more pronounced with small data sets. For more
    on this, see https://www.elastic.co/blog/understanding-query-then-fetch-vs-dfs-query-then-fetch.

    Use search_type=dfs_query_then_fetch to counteract this effect when querying
    Elasticsearch while debugging. The search_type parameter must be passed in the
    querystring. For more, see https://www.elastic.co/guide/en/elasticsearch/reference/1.5/search-request-body.html
    and https://www.elastic.co/guide/en/elasticsearch/reference/1.5/search-request-search-type.html.

    To see how a given hit's score was computed, use the explain parameter:
    https://www.elastic.co/guide/en/elasticsearch/reference/1.5/search-request-explain.html
    """
    elasticsearch_boost_config = {
        'function_score': {
            'boost_mode': 'sum',
            'boost': 1.0,
            'score_mode': 'sum',
            'functions': [
                {'filter': {'term': {'pacing_type_exact': 'self_paced'}}, 'weight': 1.0},
                {'filter': {'term': {'type_exact': 'Professional Certificate'}}, 'weight': 1.0},
                {'filter': {'term': {'type_exact': 'MicroMasters'}}, 'weight': 1.0},

                # Decay function for modifying scores based on the value of the
                # start field. The Gaussian function decays slowly, then rapidly,
                # then slowly again. This creates a cluster of high-scoring results
                # whose start field is near the present, and a spread of results
                # whose starts are further from the present, either in the past
                # or in future.
                #
                # Be careful with scales less than 30 days! Scales that are too
                # small can cause scores to quickly drop to 0, leaving you with
                # no start field boosting at all.
                #
                # For more on how decay functions work, especially if you're thinking
                # about changing this, read https://www.elastic.co/guide/en/elasticsearch/guide/1.x/decay-functions.html
                # and https://www.elastic.co/guide/en/elasticsearch/reference/1.5/query-dsl-function-score-query.html#_decay_functions.
                #
                # For help visualizing the effect different decay functions can
                # have on relevance scores, try https://codepen.io/xyu/full/MyQYjN.
                {
                    'gauss': {
                        'start': {
                            'origin': 'now',
                            'decay': 0.95,
                            'scale': '30d'
                        }
                    },
                    'weight': 5.0
                },

                # Boost function for CourseRuns with enrollable paid Seats.
                # We want to boost if:
                #       - The course run has at least one enrollable paid Seat (has_enrollable_paid_seats is True)
                # AND one of the following two conditions are true
                #       - The paid_seat_enrollment_end is unspecified.
                #       - The paid_seat_enrollment_end is in the future.
                # We apply a weight of 1.0 to match the boost given for self paced courses.
                {
                    'filter': {
                        'bool': {
                            'must': [
                                {'exists': {'field': 'has_enrollable_paid_seats'}},
                                {'term': {'has_enrollable_paid_seats': True}}
                            ],
                            'should': [
                                {'bool': {'must_not': {'exists': {'field': 'paid_seat_enrollment_end'}}}},
                                {'range': {'paid_seat_enrollment_end': {'gte': 'now'}}}
                            ]
                        }
                    },
                    'weight': 1.0
                },

                # Boost function for enrollable CourseRuns.
                # We want to boost if:
                #   - enrollment_start and enrollment_end are unspecified
                #   - enrollment_start is unspecified and enrollment_end is in the future
                #   - enrollment_end is unspecified and enrollment_start is in the past
                #   - enrollment_start is in the past and enrollment_end is in the future
                # We apply a weight of 1.0 to match the boost given for self paced and enrollable paid courses.
                {
                    'filter': {
                        'bool': {
                            'should': [
                                {'bool': {
                                    'must_not': [
                                        {'exists': {'field': 'enrollment_start'}},
                                        {'exists': {'field': 'enrollment_end'}}
                                    ]
                                }},
                                {'bool': {
                                    'must_not': {'exists': {'field': 'enrollment_start'}},
                                    'must': [
                                        {'exists': {'field': 'enrollment_end'}},
                                        {'range': {'enrollment_end': {'gt': 'now'}}}
                                    ]
                                }},
                                {'bool': {
                                    'must_not': {'exists': {'field': 'enrollment_end'}},
                                    'must': [
                                        {'exists': {'field': 'enrollment_start'}},
                                        {'range': {'enrollment_start': {'lte': 'now'}}}
                                    ]
                                }},
                                {'bool': {
                                    'must': [
                                        {'exists': {'field': 'enrollment_start'}},
                                        {'exists': {'field': 'enrollment_end'}},
                                        {'range': {'enrollment_start': {'lte': 'now'}}},
                                        {'range': {'enrollment_end': {'gt': 'now'}}}
                                    ]
                                }}
                            ]
                        }
                    },
                    'weight': 1.0
                }
            ]
        }
    }
    return elasticsearch_boost_config
