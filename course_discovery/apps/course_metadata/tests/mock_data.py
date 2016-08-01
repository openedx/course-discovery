# A course which exists, but has no associated runs
EXISTING_COURSE = {
    'course_key': 'PartialX+P102',
    'title': 'A partial course',
}

EXISTING_COURSE_AND_RUN_DATA = (
    {
        'course_run_key': 'course-v1:SC+BreadX+3T2015',
        'course_key': 'SC+BreadX',
        'title': 'Bread Baking 101',
        'current_language': 'en-us',
    },
    {
        'course_run_key': 'course-v1:TX+T201+3T2015',
        'course_key': 'TX+T201',
        'title': 'Testing 201',
        'current_language': ''
    }
)

ORPHAN_ORGANIZATION_KEY = 'orphan_org'

ORPHAN_STAFF_KEY = 'orphan_staff'

COURSES_API_BODIES = [
    {
        'end': '2015-08-08T00:00:00Z',
        'enrollment_start': '2015-05-15T13:00:00Z',
        'enrollment_end': '2015-06-29T13:00:00Z',
        'id': 'course-v1:MITx+0.111x+2T2015',
        'media': {
            'image': {
                'raw': 'http://example.com/image.jpg',
            },
        },
        'name': 'Making Science and Engineering Pictures: A Practical Guide to Presenting Your Work',
        'number': '0.111x',
        'org': 'MITx',
        'short_description': '',
        'start': '2015-06-15T13:00:00Z',
        'pacing': 'self',
    },
    {
        'effort': None,
        'end': '2015-12-11T06:00:00Z',
        'enrollment_start': None,
        'enrollment_end': None,
        'id': 'course-v1:KyotoUx+000x+2T2016',
        'media': {
            'course_image': {
                'uri': '/asset-v1:KyotoUx+000x+2T2016+type@asset+block@000x-course_imagec-378x225.jpg'
            },
            'course_video': {
                'uri': None
            }
        },
        'name': 'Evolution of the Human Sociality: A Quest for the Origin of Our Social Behavior',
        'number': '000x',
        'org': 'KyotoUx',
        'short_description': '',
        'start': '2015-10-29T09:00:00Z',
        'pacing': 'instructor,'
    },
    {
        # Add a second run of KyotoUx+000x (3T2016) to test merging data across
        # multiple course runs into a single course.
        'effort': None,
        'end': None,
        'enrollment_start': None,
        'enrollment_end': None,
        'id': 'course-v1:KyotoUx+000x+3T2016',
        'media': {
            'course_image': {
                'uri': '/asset-v1:KyotoUx+000x+3T2016+type@asset+block@000x-course_imagec-378x225.jpg'
            },
            'course_video': {
                'uri': None
            }
        },
        'name': 'Evolution of the Human Sociality: A Quest for the Origin of Our Social Behavior',
        'number': '000x',
        'org': 'KyotoUx',
        'short_description': '',
        'start': None,
    },
]

ECOMMERCE_API_BODIES = [
    {
        "id": "audit/course/run",
        "products": [
            {
                "structure": "parent",
                "price": None,
                "expires": None,
                "attribute_values": [],
                "is_available_to_buy": False,
                "stockrecords": []
            },
            {
                "structure": "child",
                "expires": None,
                "attribute_values": [],
                "stockrecords": [
                    {
                        "price_currency": "USD",
                        "price_excl_tax": "0.00",
                    }
                ]
            }
        ]
    },
    {
        "id": "verified/course/run",
        "products": [
            {
                "structure": "parent",
                "price": None,
                "expires": None,
                "attribute_values": [],
                "is_available_to_buy": False,
                "stockrecords": []
            },
            {
                "structure": "child",
                "expires": None,
                "attribute_values": [
                    {
                        "name": "certificate_type",
                        "value": "honor"
                    }
                ],
                "stockrecords": [
                    {
                        "price_currency": "EUR",
                        "price_excl_tax": "0.00",
                    }
                ]
            },
            {
                "structure": "child",
                "expires": "2017-01-01T12:00:00Z",
                "attribute_values": [
                    {
                        "name": "certificate_type",
                        "value": "verified"
                    }
                ],
                "stockrecords": [
                    {
                        "price_currency": "EUR",
                        "price_excl_tax": "25.00",
                    }
                ]
            }
        ]
    },
    {
        # This credit course has two credit seats to verify we are correctly finding/updating using the credit
        # provider field.
        "id": "credit/course/run",
        "products": [
            {
                "structure": "parent",
                "price": None,
                "expires": None,
                "attribute_values": [],
                "is_available_to_buy": False,
                "stockrecords": []
            },
            {
                "structure": "child",
                "expires": None,
                "attribute_values": [],
                "stockrecords": [
                    {
                        "price_currency": "USD",
                        "price_excl_tax": "0.00",
                    }
                ]
            },
            {
                "structure": "child",
                "expires": "2017-01-01T12:00:00Z",
                "attribute_values": [
                    {
                        "name": "certificate_type",
                        "value": "verified"
                    }
                ],
                "stockrecords": [
                    {
                        "price_currency": "USD",
                        "price_excl_tax": "25.00",
                    }
                ]
            },
            {
                "structure": "child",
                "expires": "2017-06-01T12:00:00Z",
                "attribute_values": [
                    {
                        "name": "certificate_type",
                        "value": "credit"
                    },
                    {
                        "name": "credit_hours",
                        "value": 2
                    },
                    {
                        "name": "credit_provider",
                        "value": "asu"
                    },
                    {
                        "name": "verification_required",
                        "value": False
                    },
                ],
                "stockrecords": [
                    {
                        "price_currency": "USD",
                        "price_excl_tax": "250.00",
                    }
                ]
            },
            {
                "structure": "child",
                "expires": "2017-06-01T12:00:00Z",
                "attribute_values": [
                    {
                        "name": "certificate_type",
                        "value": "credit"
                    },
                    {
                        "name": "credit_hours",
                        "value": 2
                    },
                    {
                        "name": "credit_provider",
                        "value": "acme"
                    },
                    {
                        "name": "verification_required",
                        "value": False
                    },
                ],
                "stockrecords": [
                    {
                        "price_currency": "USD",
                        "price_excl_tax": "250.00",
                    }
                ]
            }
        ]
    },
    {  # Course with a currency not found in the database
        "id": "nocurrency/course/run",
        "products": [
            {
                "structure": "parent",
                "price": None,
                "expires": None,
                "attribute_values": [],
                "is_available_to_buy": False,
                "stockrecords": []
            },
            {
                "structure": "child",
                "expires": None,
                "attribute_values": [],
                "stockrecords": [
                    {
                        "price_currency": "123",
                        "price_excl_tax": "0.00",
                    }
                ]
            }
        ]
    },
    {  # Course which does not exist in LMS
        "id": "fake-course-does-not-exist",
        "products": [
            {
                "structure": "parent",
                "price": None,
                "expires": None,
                "attribute_values": [],
                "is_available_to_buy": False,
                "stockrecords": []
            },
            {
                "structure": "child",
                "expires": None,
                "attribute_values": [],
                "stockrecords": [
                    {
                        "price_currency": "USD",
                        "price_excl_tax": "0.00",
                    }
                ]
            }
        ]
    }
]

MARKETING_API_BODY = {
    'items': [
        {
            'title': EXISTING_COURSE_AND_RUN_DATA[0]['title'],
            'start': '2015-06-15T13:00:00Z',
            'end': '2015-12-15T13:00:00Z',
            'level': {
                'title': 'Introductory',
            },
            'course_about_uri': '/course/bread-baking-101',
            'course_id': EXISTING_COURSE_AND_RUN_DATA[0]['course_run_key'],
            'subjects': [{
                'title': 'Bread baking',
            }],
            'current_language': EXISTING_COURSE_AND_RUN_DATA[0]['current_language'],
            'subtitle': 'Learn about Bread',
            'description': '<p>Bread is a <a href="/wiki/Staple_food" title="Staple food">staple food</a>.',
            'sponsors': [{
                'uuid': 'abc123',
                'title': 'Tatte',
                'image': 'http://example.com/tatte.jpg',
                'uri': 'sponsor/tatte'
            }],
            'staff': [{
                'uuid': 'staff123',
                'title': 'The Muffin Man',
                'image': 'http://example.com/muffinman.jpg',
                'display_position': {
                    'title': 'Baker'
                }
            }, {
                'uuid': 'staffZYX',
                'title': 'Arthur',
                'image': 'http://example.com/kingarthur.jpg',
                'display_position': {
                    'title': 'King'
                }
            }]
        },
        {
            'title': EXISTING_COURSE_AND_RUN_DATA[1]['title'],
            'start': '2015-06-15T13:00:00Z',
            'end': '2015-12-15T13:00:00Z',
            'level': {
                'title': 'Intermediate',
            },
            'course_about_uri': '/course/testing-201',
            'course_id': EXISTING_COURSE_AND_RUN_DATA[1]['course_run_key'],
            'subjects': [{
                'title': 'testing',
            }],
            'current_language': EXISTING_COURSE_AND_RUN_DATA[1]['current_language'],
            'subtitle': 'Testing 201',
            'description': "how to test better",
            'sponsors': [],
            'staff': [{
                'uuid': '432staff',
                'title': 'Test',
                'image': 'http://example.com/test.jpg',
                'display_position': {
                    'title': 'Tester'
                }
            }]
        },
        {  # Create a course which exists in LMS/Otto, but without course runs
            'title': EXISTING_COURSE['title'],
            'start': '2015-06-15T13:00:00Z',
            'end': '2015-12-15T13:00:00Z',
            'level': {
                'title': 'Advanced',
            },
            'course_about_uri': '/course/partial-101',
            'course_id': 'course-v1:{course_key}+run'.format(course_key=EXISTING_COURSE['course_key']),
            'subjects': [{
                'title': 'partially fake',
            }],
            'current_language': 'en-us',
            'subtitle': 'Nope',
            'description': 'what is fake?',
            'sponsors': [{
                'uuid': '123abc',
                'title': 'Fake',
                'image': 'http://example.com/fake.jpg',
                'uri': 'sponsor/fake'
            }, {
                'uuid': 'qwertyuiop',
                'title': 'Faux',
                'image': 'http://example.com/faux.jpg',
                'uri': 'sponsor/faux'
            }],
            'staff': [],
        },
        {  # Create a fake course run which doesn't exist in LMS/Otto
            'title': 'A partial course',
            'start': '2015-06-15T13:00:00Z',
            'end': '2015-12-15T13:00:00Z',
            'level': {
                'title': 'Advanced',
            },
            'course_about_uri': '/course/partial-101',
            'course_id': 'course-v1:fakeX+fake+reallyfake',
            'subjects': [{
                'title': 'seriously fake',
            }],
            'current_language': 'en-us',
            'subtitle': 'Nope',
            'description': 'what is real?',
            'sponsors': [],
            'staff': [],
        },
        # NOTE (CCB): Some of the entries are empty arrays. Remove this as part of ECOM-4493.
        [],
    ]
}

ORGANIZATIONS_API_BODIES = [
    {
        'name': 'edX',
        'short_name': ' edX ',
        'description': 'edX',
        'logo': 'https://example.com/edx.jpg',
    },
    {
        'name': 'Massachusetts Institute of Technology ',
        'short_name': 'MITx',
        'description': ' ',
        'logo': '',
    }
]

PROGRAMS_API_BODIES = [
    {
        'uuid': 'd9ee1a73-d82d-4ed7-8eb1-80ea2b142ad6',
        'id': 1,
        'name': 'Water Management',
        'subtitle': 'Explore water management concepts and technologies',
        'category': 'xseries',
        'status': 'active',
        'marketing_slug': 'water-management',
        'organizations': [
            {
                'display_name': 'Delft University of Technology',
                'key': 'DelftX'
            }
        ],
        'banner_image_urls': {
            'w1440h480': 'https://example.com/delft-water__1440x480.jpg',
            'w348h116': 'https://example.com/delft-water__348x116.jpg',
            'w726h242': 'https://example.com/delft-water__726x242.jpg',
            'w435h145': 'https://example.com/delft-water__435x145.jpg'
        }
    },
    {
        'uuid': 'b043f467-5e80-4225-93d2-248a93a8556a',
        'id': 2,
        'name': 'Supply Chain Management',
        'subtitle': 'Learn how to design and optimize the supply chain to enhance business performance.',
        'category': 'xseries',
        'status': 'active',
        'marketing_slug': 'supply-chain-management-0',
        'organizations': [
            {
                'display_name': 'Massachusetts Institute of Technology',
                'key': 'MITx'
            }
        ],
        'banner_image_urls': {},
    },

    # This item is invalid (due to a null marketing_slug) and will not be loaded.
    {
        'uuid': '01bc3a40-fa9d-4076-8885-660b2f7a594e',
        'id': 3,
        'name': 'Data Science and Analytics in Context',
        'subtitle': 'Learn the foundations of statistical thinking, the power of machine learning, and enabling '
                    'technologies for data science.',
        'category': 'xseries',
        'status': 'active',
        'marketing_slug': None,
        'organizations': [
            {
                'display_name': 'Columbia University',
                'key': 'ColumbiaX'
            }
        ],
        'banner_image_urls': {},
    },
]
