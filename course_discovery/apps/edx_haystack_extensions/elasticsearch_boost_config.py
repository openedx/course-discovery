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
    return {
        'function_score': {
            'boost_mode': 'sum',
            'boost': 1.0,
            'score_mode': 'sum',
            'functions': [
                {
                    'filter': {
                        'term': {
                            'pacing_type_exact': 'self_paced'
                        }
                    },
                    'weight': 5.0
                },
                {
                    'filter': {
                        'term': {
                            'type_exact': 'MicroBachelors'
                        }
                    },
                    'weight': 5.0
                },
                {
                    'filter': {
                        'term': {
                            'type_exact': 'MicroMasters'
                        }
                    },
                    'weight': 5.0
                },
                {
                    'filter': {
                        'term': {
                            'type_exact': 'Professional Certificate'
                        }
                    },
                    'weight': 5.0
                },

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

                # Reward course runs that are currently running and still upgradeable
                {
                    'filter': {
                        'bool': {
                            'must': {
                                'term': {
                                    'is_current_and_still_upgradeable': True
                                }
                            }
                        }
                    },
                    'weight': 10.0
                },

                # Reward course runs with enrollable, paid seats.
                {
                    'filter': {
                        'bool': {
                            'must': {
                                'term': {
                                    'has_enrollable_paid_seats': True
                                }
                            },
                            'should': [
                                # A paid seat with a null enrollment end date is
                                # considered to be available, as if the end date
                                # were in the future.
                                {
                                    'bool': {
                                        'must_not': {
                                            'exists': {
                                                'field': 'paid_seat_enrollment_end'
                                            }
                                        }
                                    }
                                },
                                {
                                    'range': {
                                        'paid_seat_enrollment_end': {
                                            'gte': 'now'
                                        }
                                    }
                                }
                            ]
                        }
                    },
                    'weight': 15.0
                },

                # Penalize course runs without enrollable, paid seats. This penalty
                # applies specifically to course runs, so that we don't reduce the
                # relevance score of programs.
                {
                    'filter': {
                        'bool': {
                            'must': {
                                'term': {
                                    'content_type_exact': 'courserun'
                                }
                            },
                            'must_not': {
                                'range': {
                                    'paid_seat_enrollment_end': {
                                        'gte': 'now'
                                    }
                                }
                            }
                        }
                    },
                    'weight': -20.0
                },

                # Give a slight boost to enrollable course runs, regardless of seat
                # configuration. Course runs with unexpired, paid seats should be
                # rewarded more generously, but when comparing two course runs,
                # the one in which the user can enroll should be given preference.
                {
                    'filter': {
                        'bool': {
                            'should': [
                                {
                                    'bool': {
                                        'must_not': [
                                            {
                                                'exists': {
                                                    'field': 'enrollment_start'
                                                }
                                            },
                                            {
                                                'exists': {
                                                    'field': 'enrollment_end'
                                                }
                                            }
                                        ]
                                    }
                                },
                                {
                                    'bool': {
                                        'must': [
                                            {
                                                'exists': {
                                                    'field': 'enrollment_end'
                                                }
                                            },
                                            {
                                                'range': {
                                                    'enrollment_end': {
                                                        'gt': 'now'
                                                    }
                                                }
                                            }
                                        ],
                                        'must_not': {
                                            'exists': {
                                                'field': 'enrollment_start'
                                            }
                                        }
                                    }
                                },
                                {
                                    'bool': {
                                        'must': [
                                            {
                                                'exists': {
                                                    'field': 'enrollment_start'
                                                }
                                            },
                                            {
                                                'range': {
                                                    'enrollment_start': {
                                                        'lte': 'now'
                                                    }
                                                }
                                            }
                                        ],
                                        'must_not': {
                                            'exists': {
                                                'field': 'enrollment_end'
                                            }
                                        }
                                    }
                                },
                                {
                                    'bool': {
                                        'must': [
                                            {
                                                'exists': {
                                                    'field': 'enrollment_start'
                                                }
                                            },
                                            {
                                                'exists': {
                                                    'field': 'enrollment_end'
                                                }
                                            },
                                            {
                                                'range': {
                                                    'enrollment_start': {
                                                        'lte': 'now'
                                                    }
                                                }
                                            },
                                            {
                                                'range': {
                                                    'enrollment_end': {
                                                        'gt': 'now'
                                                    }
                                                }
                                            }
                                        ]
                                    }
                                }
                            ]
                        }
                    },
                    'weight': 2.0
                }
            ]
        }
    }
