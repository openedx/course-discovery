COURSES_INDEX_CONFIG = {
    'settings': {
        'analysis': {
            'analyzer': {
                'lowercase_keyword': {
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
                    'analyzer': 'lowercase_keyword'
                },
                'name': {
                    'type': 'string',
                    'analyzer': 'lowercase_keyword'
                }
            }
        }
    }
}
