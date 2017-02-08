def get_elasticsearch_boost_config():
    elasticsearch_boost_config = {
        'function_score': {
            'boost_mode': 'sum',
            'boost': 1.0,
            'score_mode': 'sum',
            'functions': [
                {'filter': {'term': {'pacing_type_exact': 'self_paced'}}, 'weight': 1.0},
                {'filter': {'term': {'type_exact': 'Professional Certificate'}}, 'weight': 1.0},
                {'filter': {'term': {'type_exact': 'MicroMasters'}}, 'weight': 1.0},
                {'linear': {'start': {'origin': 'now', 'decay': 0.95, 'scale': '1d'}}, 'weight': 5.0},

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
