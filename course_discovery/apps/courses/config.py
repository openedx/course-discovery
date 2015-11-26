COURSES_INDEX_CONFIG = {
    'settings': {
        'analysis': {
            'analyzer': {
                'case_insensitive_sort': {
                    'tokenizer': 'keyword',
                    'filter': ['lowercase']
                }
            }
        }
    },
    'mappings': {
        'course': {
            'properties': {
                'id': {
                    'type': 'string',
                    'analyzer': 'english',
                    'fields': {
                        'lowercase_sort': {
                            'type': 'string',
                            'analyzer': 'case_insensitive_sort'
                        }
                    }
                },
                'name': {
                    'type': 'string',
                    'analyzer': 'english',
                    'fields': {
                        'lowercase_sort': {
                            'type': 'string',
                            'analyzer': 'case_insensitive_sort'
                        }
                    }
                }
            }
        }
    }
}
