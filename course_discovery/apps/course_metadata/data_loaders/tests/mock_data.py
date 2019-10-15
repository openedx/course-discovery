# A course which exists, but has no associated runs
EXISTING_COURSE = {
    'course_key': 'PartialX+P102',
    'title': 'A partial course',
}

STAGE_TAG_FIELD_RESPONSE_DATA = [
    {
        'uri': 'https://www.edx.org/taxonomy_term/1721',
        'id': '1721',
        'resource': 'taxonomy_term',
        'uuid': 'c53b2abf-d4bd-429f-a0a5-211aac95487d'
    },
    {
        'uri': 'https://www.edx.org/taxonomy_term/1706',
        'id': '1706',
        'resource': 'taxonomy_term',
        'uuid': '57dc60cb-e05c-464c-900f-333d60d249d1'
    }
]

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
        'mobile_available': True,
        'hidden': False,
        'license': '',
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
        'pacing': 'instructor,',
        'mobile_available': False,
        'hidden': False,
        'license': 'all-rights-reserved',
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
        'mobile_available': None,
        'hidden': True,
    },
]

COURSES_API_BODY_ORIGINAL = {
    'effort': None,
    'end': None,
    'enrollment_start': '2015-05-15T13:00:00Z',
    'enrollment_end': '2015-06-29T13:00:00Z',
    'id': 'course-v1:KyotoUx+000x+3T2016',
    'media': {
        'course_image': {
            'uri': '/asset-v1:KyotoUx+000x+3T2016+type@asset+block@000x-course_imagec-378x225.jpg'
        },
        'course_video': {
            'uri': None
        }
    },
    'name': 'Evolution of the Human Sociality ORIGINAL',
    'number': '000x',
    'org': 'KyotoUx',
    'short_description': '',
    'start': None,
    'mobile_available': None,
    'hidden': False,
}

COURSES_API_BODY_SECOND = {
    'effort': None,
    'end': None,
    'enrollment_start': None,
    'enrollment_end': None,
    'id': 'course-v1:KyotoUx+000x+1T2020',
    'media': {
        'course_image': {
            'uri': '/asset-v1:KyotoUx+000x+1T2020+type@asset+block@000x-course_imagec-378x225.jpg'
        },
        'course_video': {
            'uri': None
        }
    },
    'name': 'Evolution of the Human Sociality SECOND',
    'number': '000x',
    'org': 'KyotoUx',
    'short_description': '',
    'start': None,
    'mobile_available': None,
    'hidden': False,
}

COURSES_API_BODY_UPDATED = {
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
    'name': 'Evolution of the Human Sociality UPDATED',
    'number': '000x',
    'org': 'KyotoUx',
    'short_description': '',
    'start': None,
    'mobile_available': None,
    'hidden': True,
}

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
                        "partner_sku": "sku001",
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
                        "value": "audit"
                    }
                ],
                "stockrecords": [
                    {
                        "price_currency": "EUR",
                        "price_excl_tax": "0.00",
                        "partner_sku": "sku002",
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
                        "partner_sku": "sku003",
                    }
                ]
            },
            {
                "structure": "standalone",
                "expires": "2017-01-01T12:00:00Z",
                "attribute_values": [
                    {
                        "code": "seat_type",
                        "value": "verified"
                    }
                ],
                "stockrecords": [
                    {
                        "price_currency": "EUR",
                        "price_excl_tax": "25.00",
                        "partner_sku": "sku004"
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
                        "partner_sku": "sku005",
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
                        "partner_sku": "sku006",
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
                        "partner_sku": "sku007",
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
                        "partner_sku": "sku008",
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
                        "partner_sku": "sku009",
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
                        "partner_sku": "sku010",
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
            'image': 'http://example.com/course1-image.jpg',
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
            'image': 'http://example.com/course1-image.jpg',
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
            'image': 'http://example.com/course2-detail.jpg',
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
    },
    {
        'name': 'Delft University of Technology',
        'short_name': 'DelftX',
        'description': ' ',
        'logo': '',
    },
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
        },
        'course_codes': [
            {
                'display_name': 'Introduction to Water and Climate',
                'key': 'CTB3300WCx',
                'organization': {
                    'display_name': 'Delft University of Technology',
                    'key': 'DelftX'
                },
                'run_modes': [
                    {
                        'course_key': 'course-v1:Delftx+CTB3300WCx+2015_T3',
                        'mode_slug': 'verified',
                        'sku': 'EFF47EC',
                        'start_date': '2015-11-05T07:39:02.791741Z',
                        'run_key': '2015_T3'
                    },
                    {
                        'course_key': 'DelftX/CTB3300WCx/2T2014',
                        'mode_slug': 'verified',
                        'sku': '',
                        'start_date': '2014-08-26T10:00:00Z',
                        'run_key': '2T2014'
                    }
                ]
            },
            {
                'display_name': 'Introduction to the Treatment of Urban Sewage',
                'key': 'CTB3365STx',
                'organization': {
                    'display_name': 'Delft University of Technology',
                    'key': 'DelftX'
                },
                'run_modes': [
                    {
                        'course_key': 'course-v1:DelftX+CTB3365STx+1T2016',
                        'mode_slug': 'verified',
                        'sku': 'F773612',
                        'start_date': '2015-11-05T07:39:02.791741Z',
                        'run_key': '1T2016'
                    },
                    {
                        'course_key': 'DelftX/CTB3365STx/2T2015',
                        'mode_slug': 'verified',
                        'sku': '',
                        'start_date': '2015-01-27T12:00:00Z',
                        'run_key': '2T2015'
                    }
                ]
            },
            {
                'display_name': 'Introduction to Drinking Water Treatment',
                'key': 'CTB3365DWx',
                'organization': {
                    'display_name': 'Delft University of Technology',
                    'key': 'DelftX'
                },
                'run_modes': [
                    {
                        'course_key': 'course-v1:DelftX+CTB3365DWx+1T2016',
                        'mode_slug': 'verified',
                        'sku': '61B1920',
                        'start_date': '2015-11-05T07:39:02.791741Z',
                        'run_key': '1T2016'
                    },
                    {
                        'course_key': 'DelftX/CTB3365DWx/3T2014',
                        'mode_slug': 'verified',
                        'sku': '',
                        'start_date': '2014-10-28T12:00:00Z',
                        'run_key': '3T2014'
                    }
                ]
            }
        ],
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
        'course_codes': [
            {
                'display_name': 'Supply Chain and Logistics Fundamentals',
                'key': 'CTL.SC1x_1',
                'organization': {
                    'display_name': 'the Massachusetts Institute of Technology',
                    'key': 'MITx'
                },
                'run_modes': [
                    {
                        'course_key': 'course-v1:MITx+CTL.SC1x_1+2T2015',
                        'mode_slug': 'verified',
                        'sku': '',
                        'start_date': '2015-05-27T00:00:00Z',
                        'run_key': '2T2015'
                    },
                    {
                        'course_key': 'MITx/ESD.SCM1x/3T2014',
                        'mode_slug': 'verified',
                        'sku': '',
                        'start_date': '2014-09-24T00:30:00Z',
                        'run_key': '3T2014'
                    }
                ]
            },
            {
                'display_name': 'Supply Chain Design',
                'key': 'CTL.SC2x',
                'organization': {
                    'display_name': 'the Massachusetts Institute of Technology',
                    'key': 'MITx'
                },
                'run_modes': [
                    {
                        'course_key': 'course-v1:MITx+CTL.SC2x+3T2015',
                        'mode_slug': 'verified',
                        'sku': '',
                        'start_date': '2015-09-30T00:00:00Z',
                        'run_key': '3T2015'
                    }
                ]
            },
            {
                'display_name': 'Supply Chain Dynamics',
                'key': 'CTL.SC3x',
                'organization': {
                    'display_name': 'the Massachusetts Institute of Technology',
                    'key': 'MITx'
                },
                'run_modes': [
                    {
                        'course_key': 'course-v1:MITx+CTL.SC3x+2T2016',
                        'mode_slug': 'verified',
                        'sku': '',
                        'start_date': '2016-05-18T00:00:00Z',
                        'run_key': '2T2016'
                    }
                ]
            }
        ],
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

ANALYTICS_API_COURSE_SUMMARIES_BODIES = [
    {
        'course_id': '00test/00test/00test',
        'count': '5',
        'recent_count_change': '2'
    },
    {
        'course_id': '00test/00test/01test',
        'count': '6',
        'recent_count_change': '1'
    },
    {
        'course_id': '00test/01test/00test',
        'count': '6',
        'recent_count_change': '1'
    },
    {
        'course_id': '00test/01test/01test',
        'count': '6',
        'recent_count_change': '1'
    },
    {
        'course_id': '00test/01test/02test',
        'count': '11',
        'recent_count_change': '4'
    },
    {
        'course_id': '00test/02test/00test',
        'count': '111111',
        'recent_count_change': '111'
    }
]

MARKETING_SITE_API_XSERIES_BODIES = [
    {
        'body': {
            'value': '<h3><span>XSeries Program Overview</span></h3> <p>Safe water supply and hygienic water '
                     'treatment are prerequisites for the well-being of communities all over the world. This '
                     'Water XSeries, offered by the water management experts of TU Delft, will give you a unique '
                     'opportunity to gain access to world-class knowledge and expertise in this field.</p> <p>'
                     'This 3-course series will cover questions such as: How does climate change affect water '
                     'cycle and public safety? How to use existing technologies to treat groundwater and surface '
                     'water so we have safe drinking water? How do we take care of sewage produced in the cities '
                     'on a daily basis? You will learn what are the physical, chemical and biological processes '
                     'involved; carry out simple experiments at home; and have the chance to make a basic design '
                     'of a drinking water treatment plant</p>',
            'summary': '',
            'format': 'standard_html'
        },
        'field_xseries_banner_image': {
            'fid': '66321',
            'name': 'waterxseries_course_image.jpg',
            'mime': 'image/jpeg',
            'size': '399725',
            'url': 'https://www.edx.org/sites/default/files/xseries/image/banner/waterxseries_course_image.jpg',
            'timestamp': '1439307542',
            'owner': {
                'uri': 'https://www.edx.org/user/10296',
                'id': '10296',
                'resource': 'user',
                'uuid': '45b915f3-5307-4fe0-b2ea-55ae92a2b078'
            },
            'uuid': '79c103b4-98a1-4133-8b5d-665542997684'
        },
        'field_xseries_institutions': [
            {

                'node_id': '637',
                'type': 'school',
                'title': 'DelftX',
                'language': 'und',
                'url': 'https://www.edx.org/school/delftx',
                'body': [],
                'uuid': 'c484a523-d396-4aff-90f4-bb7e82e16bf6',
                'vuuid': '7a5d8dba-9876-4d13-a4f8-75abbe1efa0b'
            }
        ],
        'field_course_level': 'Introductory',
        'field_card_image': {
            'fid': '66771',
            'name': 'waterxseries_course0.png',
            'mime': 'image/png',
            'size': '193569',
            'url': 'https://www.edx.org/sites/default/files/card/images/waterxseries_course0.png',
            'timestamp': '1439410202',
            'owner': {
                'uri': 'https://www.edx.org/user/10296',
                'id': '10296',
                'resource': 'user',
                'uuid': '45b915f3-5307-4fe0-b2ea-55ae92a2b078'
            },
            'uuid': '84e07f7f-0f42-44b3-b9f6-d24cde1d7618'
        },
        'field_cards_section_description': 'The courses in this series have been designed to be taken in order.'
                                           ' The first six courses must be completed before enrolling in the capstone.'
                                           '\r\n\r\nIf you are planning to complete both the UX Research and UX Design '
                                           'XSeries, you can start with either one! When you have completed one, you '
                                           'can take the remaining courses in the second series.',
        'field_xseries_overview': {
            'value': '<h3>What You\'ll Learn</h3> <ul><li>An understanding of the global water cycle and its '
                     'various processes</li> <li>The mechanisms of climate change and their effects on water '
                     'systems</li> <li>Drinking treatment and quality of groundwater and surfacewater</li> <li>'
                     'The major pollutants that are present in the sewage</li> <li>The Physical, chemical, and '
                     'biological processes involved in water treatment and distribution</li> <li>How urban water '
                     'services function and the technologies they use</li> </ul>',
            'format': 'standard_html'
        },
        'field_xseries_subtitle': 'Explore water management concepts and technologies.',
        'field_xseries_subtitle_short': 'Explore water management concepts and technologies.',
        'type': 'xseries',
        'title': 'Water Management',
        'url': 'https://www.edx.org/xseries/water-management'
    },
    {
        'body': {
            'value': '<h3>XSeries Program Overview</h3> <p>This XSeries consists of three courses that enable '
                     'students to learn and practice the art and science of supply chain management. The '
                     'component courses build from fundamental concepts to advanced design and finally to '
                     'strategic decision making. It is ideal preparation for anyone interested in succeeding in '
                     'a career in logistics, operations, or supply chain management within any large global firm '
                     'or organization.</p>',
            'summary': '',
            'format': 'standard_html'
        },
        'field_xseries_banner_image': {
            'fid': '76876',
            'name': 'scm2x-gray-1440x260.jpg',
            'mime': 'image/jpeg',
            'size': '51626',
            'url': 'https://www.edx.org/sites/default/files/xseries/image/banner/scm2x-gray-1440x260_0.jpg',
            'timestamp': '1453500891',
            'owner': {
                'uri': 'https://www.edx.org/user/1',
                'id': '1',
                'resource': 'user',
                'uuid': '434dea4f-7b93-4cba-9965-fe4856062a4f'
            },
            'uuid': 'b0385fc9-9344-40f8-a094-b61f0ff66e54'
        },
        'field_product_video': {
            'fid': '67536',
            'name': 'EDXABVID2014-V064600',
            'mime': 'video/youtube',
            'size': '0',
            'url': 'http://www.youtube.com/watch?v=C9DG0Nlszco',
            'timestamp': '1457539040',
            'owner': {
                'uri': 'https://www.edx.org/user/10296',
                'id': '10296',
                'resource': 'user',
                'uuid': '45b915f3-5307-4fe0-b2ea-55ae92a2b078'
            },
            'uuid': '18595aea-9c45-4df1-a3e3-cf68edbbe04b'
        },
        'field_xseries_institutions': [
            {
                'title': 'MITx',
                'language': 'und',
                'url': 'https://www.edx.org/school/mitx',
                'body': [],
                'uuid': '2a73d2ce-c34a-4e08-8223-83bca9d2f01d',
                'vuuid': '2bf3a55e-cbde-4759-9199-fcb6c43a1d7a'
            }
        ],
        'field_course_level': 'Advanced',
        'field_card_image': {
            'fid': '76886',
            'name': 'banner-380x168_0.png',
            'mime': 'image/png',
            'size': '22072',
            'url': 'https://www.edx.org/sites/default/files/card/images/banner-380x168_0.png',
            'timestamp': '1453501343',
            'owner': {
                'uri': 'https://www.edx.org/user/1',
                'id': '1',
                'resource': 'user',
                'uuid': '434dea4f-7b93-4cba-9965-fe4856062a4f'
            },
            'uuid': 'a8fbba26-4fe0-4dc2-9619-448730ff171c'
        },
        'field_cards_section_description': None,
        'field_xseries_overview': {
            'value': '<h3>What You\'ll Learn</h3> <ul><li>How to make trade-offs between cost and service for '
                     'both the design and operation of supply chains using total cost equations</li> '
                     '<li>Fundamentals of demand planning from forecasting to Sales &amp; Operations Planning'
                     '</li> <li>How supply chain strategies align to overall organizational strategy</li> <li>How '
                     'supply chain activities translate into financial terms that the C-level suite understands'
                     '</li> </ul>',
            'format': 'standard_html'
        },
        'field_xseries_subtitle': 'Learn how to design and optimize the physical, financial, and information '
                                  'flows of a supply chain to enhance business performance.',
        'field_xseries_subtitle_short': 'Design and optimize the flow of a supply chain',
        'type': 'xseries',
        'title': 'Supply Chain Management',
        'url': 'https://www.edx.org/xseries/supply-chain-management-0'
    }
]

MARKETING_SITE_API_SUBJECT_BODIES = [
    {
        'body': {
            'value': 'Yay! CS!',
            'summary': '',
            'format': 'expanded_html'
        },
        'field_xseries_banner_image': {
            'url': 'https://www.edx.org/sites/default/files/cs-1440x210.jpg'
        },
        'field_subject_url_slug': 'computer-science',
        'field_subject_subtitle': {
            'value': 'Learn about computer science from the best universities and institutions around the world.',
            'format': 'basic_html'
        },
        'field_subject_card_image': {
            'url': 'https://www.edx.org/sites/default/files/subject/image/card/computer-science.jpg',
        },
        'type': 'subject',
        'title': 'Computer Science',
        'url': 'https://www.edx.org/course/subject/math',
        'uuid': 'e52e2134-a4e4-4fcb-805f-cbef40812580',
    },
    {
        'body': {
            'value': 'Take free online math courses from MIT, Caltech, Tsinghua and other leading math and science '
                     'institutions. Get introductions to algebra, geometry, trigonometry, precalculus and calculus '
                     'or get help with current math coursework and AP exam preparation.',
            'summary': '',
            'format': 'basic_html'
        },
        'field_xseries_banner_image': {
            'url': 'https://www.edx.org/sites/default/files/mathemagical-1440x210.jpg',
        },
        'field_subject_url_slug': 'math',
        'field_subject_subtitle': {
            'value': 'Learn about math and more from the best universities and institutions around the world.',
            'format': 'basic_html'
        },
        'field_subject_card_image': {
            'url': 'https://www.edx.org/sites/default/files/subject/image/card/math.jpg',
        },
        'language': 'en',  # language is intentionally added to only one of these.
        'type': 'subject',
        'title': 'Math',
        'url': 'https://www.edx.org/course/subject/math',
        'uuid': 'a669e004-cbc0-4b68-8882-234c12e1cce4',
    },
]

MARKETING_SITE_API_SCHOOL_BODIES = [
    {
        'field_school_description': {
            'value': '<p>Harvard University is devoted to excellence in teaching, learning, and '
                     'research, and to developing leaders in many disciplines who make a difference globally. '
                     'Harvard faculty are engaged with teaching and research to push the boundaries of human '
                     'knowledge. The University has twelve degree-granting Schools in addition to the Radcliffe '
                     'Institute for Advanced Study.</p>\n\n<p>Established in 1636, Harvard '
                     'is the oldest institution of higher education in the United States. The University, which '
                     'is based in Cambridge and Boston, Massachusetts, has an enrollment of over 20,000 degree '
                     'candidates, including undergraduate, graduate, and professional students. Harvard has more '
                     'than 360,000 alumni around the world.</p>',
            'format': 'standard_html'
        },
        'field_school_name': 'Harvard University',
        'field_school_image_banner': {
            'url': 'https:www.edx.org/sites/default/files/school/image/banner/harvardx.jpg',
        },
        'field_school_image_logo': {
            'url': 'https://www.edx.org/sites/default/files/school/image/banner/harvard_logo_200x101_0.png',
        },
        'field_school_subdomain_prefix': 'harvard',
        'field_school_url_slug': 'harvardx',
        'field_school_is_school': True,
        'field_school_is_partner': False,
        'field_school_is_contributor': False,
        'field_school_is_charter': True,
        'field_school_is_founder': True,
        'field_school_is_display': True,
        'field_school_is_affiliate': False,
        'type': 'school',
        'title': 'HarvardX',
        'url': 'https://www.edx.org/school/harvardx',
        'uuid': '44022f13-20df-4666-9111-cede3e5dc5b6',
    },
    {
        'field_school_description': {
            'value': '<p>Massachusetts Institute of Technology \u2014 a coeducational, privately '
                     'endowed research university founded in 1861 \u2014 is dedicated to advancing knowledge '
                     'and educating students in science, technology, and other areas of scholarship that will '
                     'best serve the nation and the world in the 21st century. <a href=\u0022http://web.'
                     'mit.edu/aboutmit/\u0022 target=\u0022_blank\u0022>Learn more about MIT</a>'
                     '. Through MITx, the Institute furthers its commitment to improving education worldwide.'
                     '</p>\n\n<p><strong>MITx Courses</strong><br '
                     '/>\nMITx courses embody the inventiveness, openness, rigor and quality that are '
                     'hallmarks of MIT, and many use materials developed for MIT residential courses in the '
                     'Institute\u0027s five schools and 33 academic disciplines. Browse MITx courses below.'
                     '</p>\n\n<p>\u00a0</p>',
        },
        'field_school_name': 'MIT',
        'field_school_image_banner': {
            'url': 'https://www.edx.org/sites/default/files/school/image/banner/mit-home-banner_0.jpg',
        },
        'field_school_image_logo': {
            'url': 'https://www.edx.org/sites/default/files/school/image/banner/mit_logo_200x101_0.png',
        },
        'field_school_url_slug': 'mitx',
        'field_school_is_school': True,
        'field_school_is_partner': False,
        'field_school_is_contributor': False,
        'field_school_is_charter': True,
        'field_school_is_founder': True,
        'field_school_is_display': True,
        'field_school_is_affiliate': False,
        'type': 'school',
        'title': 'MITx',
        'url': 'https://www.edx.org/school/mitx',
        'uuid': '2a73d2ce-c34a-4e08-8223-83bca9d2f01d'
    },
]

MARKETING_SITE_API_SPONSOR_BODIES = [
    {
        'body': [],
        'field_sponsorer_image': {
            'url': 'https://www.edx.org/sites/default/files/sponsorer/image/trkcll.jpg',
        },
        'type': 'sponsorer',
        'title': 'Turkcell Akademi',
        'url': 'https://www.edx.org/sponsorer/turkcell-akademi',
        'uuid': 'fcb48e7e-8f1b-4d4b-8bb0-77617aaad9ba'
    },
    {
        'body': [],
        'field_sponsorer_image': {
            'url': 'https://www.edx.org/sites/default/files/sponsorer/image/databricks.png'
        },
        'type': 'sponsorer',
        'title': 'Databricks',
        'url': 'https://www.edx.org/sponsorer/databricks',
        'uuid': '1d86977a-0661-44c9-8f39-32bbf8ca7d4b',
    },
    {
        'body': {
            'value': 'UC Berkeley is partnering with the U.S. Department of State to extend the reach of College '
                     'Writing 2X',
        },
        'field_sponsorer_image': {
            'url': 'https://www.edx.org/sites/default/files/sponsorer/image/usdos-logo-seal.png',
        },
        'type': 'sponsorer',
        'title': 'The U.S. Department of State',
        'url': 'https://www.edx.org/sponsorer/u-s-department-state',
        'uuid': 'db53bc49-bac0-4efe-8d77-1a2d8d185024'
    },
]

UNIQUE_MARKETING_SITE_API_COURSE_BODIES = [
    {
        'field_course_code': 'CS50x',
        'field_course_course_title': {
            'value': 'Introduction to Computer Science',
            'format': None
        },
        'field_course_description': {
            'value': '<p>CS50x is Harvard College\u0027s introduction to the intellectual enterprises of c'
                     'omputer science and the art of programming for majors and non-majors alike, with or without '
                     'prior programming experience. An entry-level course taught by David J. Malan, CS50x teaches '
                     'students how to think algorithmically and solve problems efficiently. Topics include '
                     'abstraction, algorithms, data structures, encapsulation, resource management, security, software '
                     'engineering, and web development. Languages include C, PHP, and JavaScript plus SQL, CSS, and '
                     'HTML. Problem sets inspired by real-world domains of biology, cryptography, finance, forensics, '
                     'and gaming. As of Fall 2012, the on-campus version of CS50x is Harvard\u0027s second-largest '
                     'course.</p>\n<p>This course will run again starting January 2014. <a '
                     'href=\u0022https://www.edx.org/course/harvard-university/cs50x/introduction-computer-science/1022'
                     '\u0022>Click here for the registration page</a> of the new version.</p>',
            'format': 'standard_html'
        },
        'field_course_start_date': '1350273600',
        'field_course_effort': '8 problem sets (15 - 20 hours each), 2 quizzes, 1 final project',
        'field_course_faq': [
            {
                'question': 'Will certificates be awarded?',
                'answer': '<p>Yes. Online learners who achieve a passing grade in CS50x will earn a '
                          'certificate that indicates successful completion of the course, but will not include a '
                          'specific grade. Certificates will be issued by edX under the name of HarvardX.</p>\r\n'
            }
        ],
        'field_course_school_node': [
            {
                'uri': 'https://www.edx.org/node/242',
                'id': '242',
                'resource': 'node',
                'uuid': '44022f13-20df-4666-9111-cede3e5dc5b6'
            }
        ],
        'field_course_end_date': None,
        'field_course_video': {
            'fid': '32570',
            'name': 'cs50 teaser final HD',
            'mime': 'video/youtube',
            'size': '0',
            'url': 'http://www.youtube.com/watch?v=ZAldYMFUIac',
            'timestamp': '1384349212',
            'owner': {
                'uri': 'https://www.edx.org/user/143',
                'id': '143',
                'resource': 'user',
                'uuid': '8ed4adee-6f84-4bec-8b64-20f9bfe7af0c'
            },
            'uuid': '51642ba0-ff0f-4fad-b109-e55376f35b29'
        },
        'field_course_resources': [],
        'field_course_sub_title_long': {
            'value': '<p>An introduction to the intellectual enterprises of computer science and the art of '
                     'programming.</p>\n',
            'format': 'plain_text'
        },
        'field_course_subject': [
            {
                'uri': 'https://www.edx.org/node/375',
                'id': '375',
                'resource': 'node',
                'uuid': 'e52e2134-a4e4-4fcb-805f-cbef40812580'
            },
            {
                'uri': 'https://www.edx.org/node/577',
                'id': '577',
                'resource': 'node',
                'uuid': '0d7bb9ed-4492-419a-bb44-415adafd9406'
            }
        ],
        'field_course_statement_title': None,
        'field_course_statement_body': [],
        'field_course_status': 'past',
        'field_course_start_override': None,
        'field_course_email': None,
        'field_course_syllabus': {
            'value': 'Module 1: Introducing Azure Data Catalog \n Module 2:',
            'format': 'basic_html'
        },
        'field_course_prerequisites': {
            'value': '<p>None. CS50x is designed for students with or without prior programming experience.</p>',
            'format': 'standard_html'
        },
        'field_course_staff': [
            {
                'uri': 'https://www.edx.org/node/349',
                'id': '349',
                'resource': 'node',
                'uuid': '1752b28e-8ac9-40a0-b468-326e03cafdd4'
            },
            {
                'uri': 'https://www.edx.org/node/350',
                'id': '350',
                'resource': 'node',
                'uuid': 'c5ba296e-bc91-4e5e-8d59-77f425f0863f'
            },
            {
                'uri': 'https://www.edx.org/node/351',
                'id': '351',
                'resource': 'node',
                'uuid': '6fec9136-5f1d-4205-8da2-a354c678c653'
            },
            {
                'uri': 'https://www.edx.org/node/352',
                'id': '352',
                'resource': 'node',
                'uuid': 'e1080080-98b4-4427-9004-3c331c8e6d05'
            },
            {
                'uri': 'https://www.edx.org/node/353',
                'id': '353',
                'resource': 'node',
                'uuid': 'cb6cde02-5bb3-45ab-9616-57c33d622ccc'
            }
        ],
        'field_course_staff_override': 'D. Malan, N. Hardison, R. Bowden',
        'field_course_image_promoted': {
            'fid': '32379',
            'name': 'cs50_home_tombstone.jpg',
            'mime': 'image/jpeg',
            'size': '19895',
            'url': 'https://www.edx.org/sites/default/files/course/image/promoted/cs50_home_tombstone.jpg',
            'timestamp': '1384348699',
            'owner': {
                'uri': 'https://www.edx.org/user/1',
                'id': '1',
                'resource': 'user',
                'uuid': '434dea4f-7b93-4cba-9965-fe4856062a4f'
            },
            'uuid': 'c531e644-4ca6-40ab-bddb-d41da56662a8'
        },
        'field_course_image_banner': {
            'fid': '32283',
            'name': 'cs50x-course-detail-banner.jpg',
            'mime': 'image/jpeg',
            'size': '17873',
            'url': 'https://www.edx.org/sites/default/files/course/image/banner/cs50x-course-detail-banner.jpg',
            'timestamp': '1384348498',
            'owner': {
                'uri': 'https://www.edx.org/user/1',
                'id': '1',
                'resource': 'user',
                'uuid': '434dea4f-7b93-4cba-9965-fe4856062a4f'
            },
            'uuid': '3edd5c03-853c-455c-bdcd-e4d1859ce102'
        },
        'field_course_image_tile': {
            'fid': '32473',
            'name': 'cs50x-course-listing-banner.jpg',
            'mime': 'image/jpeg',
            'size': '34535',
            'url': 'https://www.edx.org/sites/default/files/course/image/tile/cs50x-course-listing-banner.jpg',
            'timestamp': '1384348906',
            'owner': {
                'uri': 'https://www.edx.org/user/1',
                'id': '1',
                'resource': 'user',
                'uuid': '434dea4f-7b93-4cba-9965-fe4856062a4f'
            },
            'uuid': 'c2998b1a-6c82-4d89-a85d-3786cdceaa6f'
        },
        'field_course_image_video': {
            'fid': '32569',
            'name': 'cs50x-video-thumbnail.jpg',
            'mime': 'image/jpeg',
            'size': '23035',
            'url': 'https://www.edx.org/sites/default/files/course/image/video/cs50x-video-thumbnail.jpg',
            'timestamp': '1384349121',
            'owner': {
                'uri': 'https://www.edx.org/user/1',
                'id': '1',
                'resource': 'user',
                'uuid': '434dea4f-7b93-4cba-9965-fe4856062a4f'
            },
            'uuid': '14e9c85d-8836-4237-a497-0059d7379bce'
        },
        'field_course_id': 'HarvardX/CS50x/2012',
        'field_course_image_sample_cert': [],
        'field_course_image_sample_thumb': [],
        'field_course_enrollment_audit': True,
        'field_course_enrollment_honor': False,
        'field_course_enrollment_verified': False,
        'field_course_xseries_enable': False,
        'field_course_statement_image': [],
        'field_course_image_card': [],
        'field_course_image_featured_card': [],
        'field_course_code_override': None,
        'field_course_video_link_mp4': [],
        'field_course_video_duration': None,
        'field_course_self_paced': False,
        'field_course_new': None,
        'field_course_registration_dates': {
            'value': '1384348442',
            'value2': None,
            'duration': None
        },
        'field_course_enrollment_prof_ed': None,
        'field_course_enrollment_ap_found': None,
        'field_cource_price': None,
        'field_course_additional_keywords': 'Free,',
        'field_course_enrollment_mobile': None,
        'field_course_part_of_products': [],
        'field_course_level': None,
        'field_course_what_u_will_learn': {
            'value': 'This is fake data for testing!'
        },
        'field_course_video_locale_lang': [],
        'field_course_languages': [],
        'field_couse_is_hidden': None,
        'field_xseries_display_override': [],
        'field_course_extra_description': [],
        'field_course_extra_desc_title': None,
        'field_course_body': [],
        'field_course_enrollment_no_id': None,
        'field_course_has_prerequisites': True,
        'field_course_enrollment_credit': None,
        'field_course_is_disabled': None,
        'field_course_tags': STAGE_TAG_FIELD_RESPONSE_DATA,
        'field_course_sub_title_short': 'An introduction to the intellectual enterprises of computer science and the '
                                        'art of programming.',
        'field_course_length_weeks': None,
        'field_course_start_date_style': None,
        'field_course_head_prom_bkg_color': None,
        'field_course_head_promo_image': [],
        'field_course_head_promo_text': [],
        'field_course_outcome': None,
        'field_course_required_weeks': None,
        'field_course_required_days': None,
        'field_course_required_hours': None,
        'nid': '254',
        'vid': '8078',
        'is_new': False,
        'type': 'course',
        'title': 'HarvardX: CS50x: Introduction to Computer Science',
        'language': 'und',
        'url': 'https://www.edx.org/course/introduction-computer-science-harvardx-cs50x-1',
        'edit_url': 'https://www.edx.org/node/254/edit',
        'status': '0',
        'promote': '0',
        'sticky': '0',
        'created': '1384348442',
        'changed': '1443028629',
        'author': {
            'uri': 'https://www.edx.org/user/143',
            'id': '143',
            'resource': 'user',
            'uuid': '8ed4adee-6f84-4bec-8b64-20f9bfe7af0c'
        },
        'log': 'Updated by FeedsNodeProcessor',
        'revision': None,
        'body': [],
        'uuid': '98da7bb8-dd9f-4747-aeb8-a068a863b9f8',
        'vuuid': 'd3363b80-b402-4d66-8637-f6540e23ad0d'
    },
    {
        'field_course_code': 'PH207x',
        'field_course_course_title': {
            'value': 'Health in Numbers: Quantitative Methods in Clinical \u0026amp; Public Health Research',
            'format': 'basic_html'
        },
        'field_course_description': {
            'value': '<h4>*Note - This is an Archived course*</h4>\n\n<p>This is a past/archived course. At this time, '
                     'you can only explore this course in a self-paced fashion. Certain features of this course may '
                     'not be active, but many people enjoy watching the videos and working with the materials. Make '
                     'sure to check for reruns of this course.</p>\n\n<hr /><p>Quantitative Methods in Clinical and '
                     'Public Health Research is the online adaptation of material from the Harvard School of Public '
                     'Health\u0027s classes in epidemiology and biostatistics. Principled investigations to monitor '
                     'and thus improve the health of individuals are firmly based on a sound understanding of modern '
                     'quantitative methods.',
            'format': 'standard_html'
        },
        'field_course_start_date': '1350273600',
        'field_course_effort': '10 hours/week',
        'field_course_school_node': [
            {
                'uri': 'https://www.edx.org/node/242',
                'id': '242',
                'resource': 'node',
                'uuid': '44022f13-20df-4666-9111-cede3e5dc5b6'
            }
        ],
        'field_course_end_date': '1358053200',
        'field_course_video': {
            'fid': '32572',
            'name': 'PH207x Intro Video - Fall 2012',
            'mime': 'video/youtube',
            'size': '0',
            'url': 'http://www.youtube.com/watch?v=j9CqWffkVNw',
            'timestamp': '1384349121',
            'owner': {
                'uri': 'https://www.edx.org/user/143',
                'id': '143',
                'resource': 'user',
                'uuid': '8ed4adee-6f84-4bec-8b64-20f9bfe7af0c'
            },
            'uuid': '2869f990-324e-41f5-8787-343e72d6134d'
        },
        'field_course_resources': [],
        'field_course_sub_title_long': {
            'value': '<p>PH207x is the online adaptation of material from the Harvard School of Public Health'
                     '\u0026#039;s classes in epidemiology and biostatistics.</p>\n',
            'format': 'plain_text'
        },
        'field_course_subject': [
            {
                'uri': 'https://www.edx.org/node/651',
                'id': '651',
                'resource': 'node',
                'uuid': '51a13a1c-7fc8-42a6-9e96-6636d10056e2'
            },
            {
                'uri': 'https://www.edx.org/node/376',
                'id': '376',
                'resource': 'node',
                'uuid': 'a669e004-cbc0-4b68-8882-234c12e1cce4'
            },
            {
                'uri': 'https://www.edx.org/node/657',
                'id': '657',
                'resource': 'node',
                'uuid': 'a5db73b2-05b4-4284-beef-c7876ec1499b'
            },
            {
                'uri': 'https://www.edx.org/node/658',
                'id': '658',
                'resource': 'node',
                'uuid': 'a168a80a-4b6c-4d92-9f1d-4c235206feaf'
            }
        ],
        'field_course_statement_title': None,
        'field_course_statement_body': [],
        'field_course_status': 'past',
        'field_course_start_override': None,
        'field_course_email': None,
        'field_course_syllabus': [],
        'field_course_prerequisites': {
            'value': '<p>Students should have a sound grasp of algebra.</p>',
            'format': 'standard_html'
        },
        'field_course_staff': [
            {
                'uri': 'https://www.edx.org/node/355',
                'id': '355',
                'resource': 'node',
                'uuid': 'f4fe549c-6290-44ad-9be2-4b48692bd233'
            },
            {
                'uri': 'https://www.edx.org/node/356',
                'id': '356',
                'resource': 'node',
                'uuid': 'fa26fc74-28ce-4b21-97b6-0799e947ce3a'
            }
        ],
        'field_course_staff_override': 'E. F. Cook, M. Pagano',
        'field_course_image_promoted': {
            'fid': '32380',
            'name': 'ph207x-home-page-promotion.jpg',
            'mime': 'image/jpeg',
            'size': '99225',
            'url': 'https://www.edx.org/sites/default/files/course/image/promoted/ph207x-home-page-promotion.jpg',
            'timestamp': '1384348699',
            'owner': {
                'uri': 'https://www.edx.org/user/1',
                'id': '1',
                'resource': 'user',
                'uuid': '434dea4f-7b93-4cba-9965-fe4856062a4f'
            },
            'uuid': '24da5041-ada5-4bb6-b0b0-099c8f3b4dc5'
        },
        'field_course_image_banner': {
            'fid': '32284',
            'name': 'ph207x-detail-banner.jpg',
            'mime': 'image/jpeg',
            'size': '21145',
            'url': 'https://www.edx.org/sites/default/files/course/image/banner/ph207x-detail-banner.jpg',
            'timestamp': '1384348498',
            'owner': {
                'uri': 'https://www.edx.org/user/1',
                'id': '1',
                'resource': 'user',
                'uuid': '434dea4f-7b93-4cba-9965-fe4856062a4f'
            },
            'uuid': '4f1f88eb-9f24-44f2-8f40-f5893c41566f'
        },
        'field_course_image_tile': {
            'fid': '32474',
            'name': 'ph207x-listing-banner.jpg',
            'mime': 'image/jpeg',
            'size': '30833',
            'url': 'https://www.edx.org/sites/default/files/course/image/tile/ph207x-listing-banner.jpg',
            'timestamp': '1384348906',
            'owner': {
                'uri': 'https://www.edx.org/user/1',
                'id': '1',
                'resource': 'user',
                'uuid': '434dea4f-7b93-4cba-9965-fe4856062a4f'
            },
            'uuid': 'eeed52c1-79c8-422a-acd1-11ba9d985bc3'
        },
        'field_course_image_video': {
            'fid': '32571',
            'name': 'ph207x-video-thumbnail.jpg',
            'mime': 'image/jpeg',
            'size': '15015',
            'url': 'https://www.edx.org/sites/default/files/course/image/video/ph207x-video-thumbnail.jpg',
            'timestamp': '1384349121',
            'owner': {
                'uri': 'https://www.edx.org/user/1',
                'id': '1',
                'resource': 'user',
                'uuid': '434dea4f-7b93-4cba-9965-fe4856062a4f'
            },
            'uuid': '2fbd2e9b-4f19-4c1a-aa03-e25d26bf53c1'
        },
        'field_course_id': 'HarvardX/PH207x/2012_Fall',
        'field_course_image_sample_cert': [],
        'field_course_image_sample_thumb': [],
        'field_course_enrollment_audit': False,
        'field_course_enrollment_honor': True,
        'field_course_enrollment_verified': False,
        'field_course_xseries_enable': False,
        'field_course_statement_image': [],
        'field_course_image_card': [],
        'field_course_image_featured_card': {
            'fid': '54386',
            'name': 'ph207x_378x225.jpg',
            'mime': 'image/jpeg',
            'size': '12250',
            'url': 'https://www.edx.org/sites/default/files/course/image/featured-card/ph207x_378x225.jpg',
            'timestamp': '1427916395',
            'owner': {
                'uri': 'https://www.edx.org/user/1781',
                'id': '1781',
                'resource': 'user',
                'uuid': '22d74975-3826-4549-99e0-91cf86801c54'
            },
            'uuid': 'e7a1b891-d680-41cb-aa0b-7e9eb4f52b3a'
        },
        'field_course_code_override': None,
        'field_course_video_link_mp4': [],
        'field_course_video_duration': None,
        'field_course_self_paced': False,
        'field_course_new': False,
        'field_course_registration_dates': {
            'value': '1384318800',
            'value2': '1384318800',
            'duration': 0
        },
        'field_course_enrollment_prof_ed': False,
        'field_course_enrollment_ap_found': False,
        'field_cource_price': None,
        'field_course_additional_keywords': 'Free,',
        'field_course_enrollment_mobile': False,
        'field_course_part_of_products': [],
        'field_course_level': 'Intermediate',
        'field_course_video_locale_lang': [
            {
                'tid': '281',
                'name': 'English',
                'description': '',
                'weight': '0',
                'node_count': 10,
                'url': 'https://www.edx.org/video-languages/english',
                'vocabulary': {
                    'uri': 'https://www.edx.org/taxonomy_vocabulary/21',
                    'id': '21',
                    'resource': 'taxonomy_vocabulary'
                },
                'parent': [],
                'parents_all': [
                    {
                        'tid': '281',
                        'name': 'English',
                        'description': '',
                        'weight': '0',
                        'node_count': 10,
                        'url': 'https://www.edx.org/video-languages/english',
                        'vocabulary': {
                            'uri': 'https://www.edx.org/taxonomy_vocabulary/21',
                            'id': '21',
                            'resource': 'taxonomy_vocabulary'
                        },
                        'parent': [],
                        'parents_all': [
                            {
                                'uri': 'https://www.edx.org/taxonomy_term/281',
                                'id': '281',
                                'resource': 'taxonomy_term',
                                'uuid': 'b8155d9c-126f-4661-9518-c4d798b0a21f'
                            }
                        ],
                        'uuid': 'b8155d9c-126f-4661-9518-c4d798b0a21f'
                    }
                ],
                'uuid': 'b8155d9c-126f-4661-9518-c4d798b0a21f'
            }
        ],
        'field_course_languages': [
            {
                'field_language_tag': 'en',
                'tid': '321',
                'name': 'English',
                'description': '',
                'weight': '0',
                'node_count': 10,
                'url': 'https://www.edx.org/course-languages/english',
                'vocabulary': {
                    'uri': 'https://www.edx.org/taxonomy_vocabulary/26',
                    'id': '26',
                    'resource': 'taxonomy_vocabulary'
                },
                'parent': [],
                'parents_all': [
                    {
                        'field_language_tag': 'en',
                        'tid': '321',
                        'name': 'English',
                        'description': '',
                        'weight': '0',
                        'node_count': 10,
                        'url': 'https://www.edx.org/course-languages/english',
                        'vocabulary': {
                            'uri': 'https://www.edx.org/taxonomy_vocabulary/26',
                            'id': '26',
                            'resource': 'taxonomy_vocabulary'
                        },
                        'parent': [],
                        'parents_all': [
                            {
                                'uri': 'https://www.edx.org/taxonomy_term/321',
                                'id': '321',
                                'resource': 'taxonomy_term',
                                'uuid': '55a95f47-6ebd-475b-853a-3aff18024c1c'
                            }
                        ],
                        'uuid': '55a95f47-6ebd-475b-853a-3aff18024c1c'
                    }
                ],
                'uuid': '55a95f47-6ebd-475b-853a-3aff18024c1c'
            }
        ],
        'field_couse_is_hidden': False,
        'field_xseries_display_override': [],
        'field_course_extra_description': [],
        'field_course_extra_desc_title': None,
        'field_course_body': {
            'value': '<p>Quantitative Methods in Clinical and Public Health Research is the online adaptation of '
                     'material from the Harvard T.H. Chan School of Public Health\u0027s classes in epidemiology and '
                     'biostatistics. Principled investigations to monitor and thus improve the health of individuals '
                     'are firmly based on a sound understanding of modern quantitative methods. This involves the '
                     'ability to discover patterns and extract knowledge from health data on a sample of individuals '
                     'and then to infer, with measured uncertainty, the unobserved population characteristics. This '
                     'course will address this need by covering the principles of biostatistics and epidemiology used '
                     'for public health and clinical research. These include outcomes measurement, measures of '
                     'associations between outcomes and their determinants, study design options, bias and '
                     'confounding, probability and diagnostic tests, confidence intervals and hypothesis testing, '
                     'power and sample size determinations, life tables and survival methods, regression methods '
                     '(both, linear and logistic), and sample survey techniques. Students will analyze sample data '
                     'sets to acquire knowledge of appropriate computer software. By the end of the course the '
                     'successful student should have attained a sound understanding of these methods and a solid '
                     'foundation for further study.<br />\n\u00a0</p>',
            'summary': '',
            'format': 'standard_html'
        },
        'field_course_enrollment_no_id': False,
        'field_course_has_prerequisites': True,
        'field_course_enrollment_credit': False,
        'field_course_is_disabled': None,
        'field_course_tags': STAGE_TAG_FIELD_RESPONSE_DATA,
        'field_course_sub_title_short': 'PH207x is the online adaptation of material from the Harvard School of Public '
                                        'Health\u0027s classes in epidemiology and biostatistics.',
        'field_course_length_weeks': '13 weeks',
        'field_course_start_date_style': None,
        'field_course_head_prom_bkg_color': None,
        'field_course_head_promo_image': [],
        'field_course_head_promo_text': [],
        'field_course_outcome': None,
        'field_course_required_weeks': '4',
        'field_course_required_days': '0',
        'field_course_required_hours': '0',
        'nid': '354',
        'vid': '112156',
        'is_new': False,
        'type': 'course',
        'title': 'HarvardX: PH207x: Health in Numbers: Quantitative Methods in Clinical \u0026 Public Health Research',
        'language': 'und',
        'url': 'https://www.edx.org/course/health-numbers-quantitative-methods-harvardx-ph207x',
        'edit_url': 'https://www.edx.org/node/354/edit',
        'status': '1',
        'promote': '0',
        'sticky': '0',
        'created': '1384348442',
        'changed': '1464108885',
        'author': {
            'uri': 'https://www.edx.org/user/143',
            'id': '143',
            'resource': 'user',
            'uuid': '8ed4adee-6f84-4bec-8b64-20f9bfe7af0c'
        },
        'log': '',
        'revision': None,
        'body': [],
        'uuid': 'aebbadcc-4e3a-4be3-a351-edaabd025ce7',
        'vuuid': '28da5064-b570-4883-8c53-330d1893ab49'
    },
    {
        'field_course_code': 'CB22x',
        'field_course_course_title': {
            'value': 'The Ancient Greek Hero',
            'format': 'basic_html'
        },
        'field_course_description': {
            'value': '<p><strong>NOTE ABOUT OUR START DATE:</strong> Although the course was launched on March 13th, '
                     'it\u0027s not too late to start participating! New participants will be joining the course until '
                     '<strong>registration closes on July 11</strong>. We offer everyone a flexible schedule and '
                     'multiple paths for participation. You can work through the course videos and readings at your '
                     'own pace to complete the associated exercises <strong>by August 26</strong>, the official course '
                     'end date. Or, you may choose to \u0022audit\u0022 the course by exploring just the particular '
                     'videos and readings that seem most suited to your interests. You are free to do as much or as '
                     'little as you would like!</p>\n<h3>\n\tOverview</h3>\n<p>What is it to be human, and how can '
                     'ancient concepts of the heroic and anti-heroic inform our understanding of the human condition? '
                     'That question is at the core of The Ancient Greek Hero, which introduces (or reintroduces) '
                     'students to the great texts of classical Greek culture by focusing on concepts of the Hero in an '
                     'engaging, highly comparative way.</p>\n<p>The classical Greeks\u0027 concepts of Heroes and the '
                     '\u0022heroic\u0022 were very different from the way we understand the term today. In this '
                     'course, students analyze Greek heroes and anti-heroes in their own historical contexts, in order '
                     'to gain an understanding of these concepts as they were originally understood while also '
                     'learning how they can inform our understanding of the human condition in general.</p>\n<p>In '
                     'Greek tradition, a hero was a human, male or female, of the remote past, who was endowed with '
                     'superhuman abilities by virtue of being descended from an immortal god. Rather than being '
                     'paragons of virtue, as heroes are viewed in many modern cultures, ancient Greek heroes had all '
                     'of the qualities and faults of their fellow humans, but on a much larger scale. Further, despite '
                     'their mortality, heroes, like the gods, were objects of cult worship \u2013 a dimension which is '
                     'also explored in depth in the course.</p>\n<p>The original sources studied in this course include'
                     ' the Homeric Iliad and Odyssey; tragedies of Aeschylus, Sophocles, and Euripides; songs of Sappho'
                     ' and Pindar; dialogues of Plato; historical texts of Herodotus; and more, including the '
                     'intriguing but rarely studied dialogue \u0022On Heroes\u0022 by Philostratus. All works are '
                     'presented in English translation, with attention to the subtleties of the original Greek. These '
                     'original sources are frequently supplemented both by ancient art and by modern comparanda, '
                     'including opera and cinema (from Jacques Offenbach\u0027s opera Tales of Hoffman to Ridley '
                     'Scott\u0027s science fiction classic Blade Runner).</p>',
            'format': 'standard_html'
        },
        'field_course_start_date': '1363147200',
        'field_course_effort': '4-6 hours / week',
        'field_course_school_node': [
            {
                'uri': 'https://www.edx.org/node/242',
                'id': '242',
                'resource': 'node',
                'uuid': '44022f13-20df-4666-9111-cede3e5dc5b6'
            }
        ],
        'field_course_end_date': '1376971200',
        'field_course_video': [],
        'field_course_resources': [],
        'field_course_sub_title_long': {
            'value': '<p>A survey of ancient Greek literature focusing on classical concepts of the hero and how they '
                     'can inform our understanding of the human condition.</p>\n',
            'format': 'plain_text'
        },
        'field_course_subject': [
            {
                'uri': 'https://www.edx.org/node/652',
                'id': '652',
                'resource': 'node',
                'uuid': 'c8579e1c-99f2-4a95-988c-3542909f055e'
            },
            {
                'uri': 'https://www.edx.org/node/653',
                'id': '653',
                'resource': 'node',
                'uuid': '00e5d5e0-ce45-4114-84a1-50a5be706da5'
            },
            {
                'uri': 'https://www.edx.org/node/655',
                'id': '655',
                'resource': 'node',
                'uuid': '74b6ed2a-3ba0-49be-adc9-53f7256a12e1'
            }
        ],
        'field_course_statement_title': None,
        'field_course_statement_body': [],
        'field_course_status': 'past',
        'field_course_start_override': None,
        'field_course_email': None,
        'field_course_syllabus': [],
        'field_course_staff': [
            {
                'uri': 'https://www.edx.org/node/564',
                'id': '564',
                'resource': 'node',
                'uuid': 'ae56688a-f2b6-4981-9aa7-5c66b68cb13e'
            },
            {
                'uri': 'https://www.edx.org/node/565',
                'id': '565',
                'resource': 'node',
                'uuid': '56d13e72-353f-48fd-9be7-6f20ef467bb7'
            },
            {
                'uri': 'https://www.edx.org/node/566',
                'id': '566',
                'resource': 'node',
                'uuid': '69a415db-3db7-436a-8d02-e571c4c4c75a'
            },
            {
                'uri': 'https://www.edx.org/node/567',
                'id': '567',
                'resource': 'node',
                'uuid': '1639460f-598c-45b7-90c2-bbdbf87cdd54'
            },
            {
                'uri': 'https://www.edx.org/node/568',
                'id': '568',
                'resource': 'node',
                'uuid': '09154d2c-7f31-477c-9d3c-d8cba9af846e'
            },
            {
                'uri': 'https://www.edx.org/node/820',
                'id': '820',
                'resource': 'node',
                'uuid': '05b7ab45-de9a-49d6-8010-04c68fc9fd55'
            },
            {
                'uri': 'https://www.edx.org/node/821',
                'id': '821',
                'resource': 'node',
                'uuid': '8a8d68c4-ab5b-40c5-b897-2d44aed2194d'
            },
            {
                'uri': 'https://www.edx.org/node/822',
                'id': '822',
                'resource': 'node',
                'uuid': 'c3e16519-a23f-4f21-908b-463375b492df'
            }
        ],
        'field_course_staff_override': 'G. Nagy, L. Muellner...',
        'field_course_image_promoted': {
            'fid': '32381',
            'name': 'tombstone_courses.jpg',
            'mime': 'image/jpeg',
            'size': '34861',
            'url': 'https://www.edx.org/sites/default/files/course/image/promoted/tombstone_courses.jpg',
            'timestamp': '1384348699',
            'owner': {
                'uri': 'https://www.edx.org/user/1',
                'id': '1',
                'resource': 'user',
                'uuid': '434dea4f-7b93-4cba-9965-fe4856062a4f'
            },
            'uuid': '1471888c-a451-4f97-9bb2-ad20c9a43c2d'
        },
        'field_course_image_banner': {
            'fid': '32285',
            'name': 'cb22x_608x211.jpg',
            'mime': 'image/jpeg',
            'size': '25909',
            'url': 'https://www.edx.org/sites/default/files/course/image/banner/cb22x_608x211.jpg',
            'timestamp': '1384348498',
            'owner': {
                'uri': 'https://www.edx.org/user/1',
                'id': '1',
                'resource': 'user',
                'uuid': '434dea4f-7b93-4cba-9965-fe4856062a4f'
            },
            'uuid': '15022bf7-e367-4a5c-b115-3755016de286'
        },
        'field_course_image_tile': {
            'fid': '32475',
            'name': 'cb22x-listing-banner.jpg',
            'mime': 'image/jpeg',
            'size': '47678',
            'url': 'https://www.edx.org/sites/default/files/course/image/tile/cb22x-listing-banner.jpg',
            'timestamp': '1384348906',
            'owner': {
                'uri': 'https://www.edx.org/user/1',
                'id': '1',
                'resource': 'user',
                'uuid': '434dea4f-7b93-4cba-9965-fe4856062a4f'
            },
            'uuid': '71735cc4-7ac3-4065-ad92-6f18f979eb0e'
        },
        'field_course_image_video': {
            'fid': '32573',
            'name': 'h_no_video_320x211_1_0.jpg',
            'mime': 'image/jpeg',
            'size': '2829',
            'url': 'https://www.edx.org/sites/default/files/course/image/video/h_no_video_320x211_1_0.jpg',
            'timestamp': '1384349121',
            'owner': {
                'uri': 'https://www.edx.org/user/1',
                'id': '1',
                'resource': 'user',
                'uuid': '434dea4f-7b93-4cba-9965-fe4856062a4f'
            },
            'uuid': '4d18789f-0909-4289-9d58-2292e5d03aee'
        },
        'field_course_id': 'HarvardX/CB22x/2013_Spring',
        'field_course_image_sample_cert': [],
        'field_course_image_sample_thumb': [],
        'field_course_enrollment_audit': True,
        'field_course_enrollment_honor': False,
        'field_course_enrollment_verified': False,
        'field_course_xseries_enable': False,
        'field_course_statement_image': [],
        'field_course_image_card': [],
        'field_course_image_featured_card': [],
        'field_course_code_override': None,
        'field_course_video_link_mp4': [],
        'field_course_video_duration': None,
        'field_course_self_paced': True,
        'field_course_new': None,
        'field_course_registration_dates': {
            'value': '1384348442',
            'value2': None,
            'duration': None
        },
        'field_course_enrollment_prof_ed': None,
        'field_course_enrollment_ap_found': None,
        'field_cource_price': None,
        'field_course_additional_keywords': 'Free,',
        'field_course_enrollment_mobile': None,
        'field_course_part_of_products': [],
        'field_course_level': None,
        'field_course_what_u_will_learn': [],
        'field_course_video_locale_lang': [],
        'field_course_languages': [],
        'field_couse_is_hidden': None,
        'field_xseries_display_override': [],
        'field_course_extra_description': [],
        'field_course_extra_desc_title': None,
        'field_course_body': [],
        'field_course_enrollment_no_id': None,
        'field_course_has_prerequisites': True,
        'field_course_enrollment_credit': None,
        'field_course_is_disabled': None,
        'field_course_tags': STAGE_TAG_FIELD_RESPONSE_DATA,
        'field_course_sub_title_short': 'A survey of ancient Greek literature focusing on classical concepts of the '
                                        'hero and how they can inform our understanding of the human condition.',
        'field_course_length_weeks': '23 weeks',
        'field_course_start_date_style': None,
        'field_course_head_prom_bkg_color': None,
        'field_course_head_promo_image': [],
        'field_course_head_promo_text': [],
        'field_course_outcome': None,
        'field_course_required_weeks': None,
        'field_course_required_days': None,
        'field_course_required_hours': None,
        'nid': '563',
        'vid': '8080',
        'is_new': False,
        'type': 'course',
        'title': 'HarvardX: CB22x: The Ancient Greek Hero',
        'language': 'und',
        'url': 'https://www.edx.org/course/ancient-greek-hero-harvardx-cb22x',
        'edit_url': 'https://www.edx.org/node/563/edit',
        'status': '0',
        'promote': '0',
        'sticky': '0',
        'created': '1384348442',
        'changed': '1443028625',
        'author': {
            'uri': 'https://www.edx.org/user/143',
            'id': '143',
            'resource': 'user',
            'uuid': '8ed4adee-6f84-4bec-8b64-20f9bfe7af0c'
        },
        'log': 'Updated by FeedsNodeProcessor',
        'revision': None,
        'body': [],
        'uuid': '6b8b779f-f567-4e98-aa41-a265d6fa073c',
        'vuuid': 'e0f8c80a-b377-4546-b247-1c94ab3a218b'
    }
]

ORIGINAL_MARKETING_SITE_API_COURSE_BODY = {
    'field_course_code': 'CB22x',
    'field_course_course_title': {
        'value': 'The Ancient Greek Hero ORIGINAL',
        'format': 'basic_html'
    },
    'field_course_description': {
        'value': 'ORIGINAL <p><b>NOTE ABOUT OUR START DATE:</b> Although the course was launched on March 13th, '
                 'it\u0027s not too late to start participating! New participants will be joining the course until '
                 '<strong>registration closes on July 11</strong>. We offer everyone a flexible schedule and '
                 'multiple paths for participation. You can work through the course videos and readings at your '
                 'own pace to complete the associated exercises <strong>by August 26</strong>, the official course '
                 'end date. Or, you may choose to \u0022audit\u0022 the course by exploring just the particular '
                 'videos and readings that seem most suited to your interests. You are free to do as much or as '
                 'little as you would like!</p>\n<h3>\n\tOverview</h3>\n<p>What is it to be human, and how can '
                 'ancient concepts of the heroic and anti-heroic inform our understanding of the human condition? '
                 'That question is at the core of The Ancient Greek Hero, which introduces (or reintroduces) '
                 'students to the great texts of classical Greek culture by focusing on concepts of the Hero in an '
                 'engaging, highly comparative way.</p>\n<p>The classical Greeks\u0027 concepts of Heroes and the '
                 '\u0022heroic\u0022 were very different from the way we understand the term today. In this '
                 'course, students analyze Greek heroes and anti-heroes in their own historical contexts, in order '
                 'to gain an understanding of these concepts as they were originally understood while also '
                 'learning how they can inform our understanding of the human condition in general.</p>\n<p>In '
                 'Greek tradition, a hero was a human, male or female, of the remote past, who was endowed with '
                 'superhuman abilities by virtue of being descended from an immortal god. Rather than being '
                 'paragons of virtue, as heroes are viewed in many modern cultures, ancient Greek heroes had all '
                 'of the qualities and faults of their fellow humans, but on a much larger scale. Further, despite '
                 'their mortality, heroes, like the gods, were objects of cult worship \u2013 a dimension which is '
                 'also explored in depth in the course.</p>\n<p>The original sources studied in this course include'
                 ' the Homeric Iliad and Odyssey; tragedies of Aeschylus, Sophocles, and Euripides; songs of Sappho'
                 ' and Pindar; dialogues of Plato; historical texts of Herodotus; and more, including the '
                 'intriguing but rarely studied dialogue \u0022On Heroes\u0022 by Philostratus. All works are '
                 'presented in English translation, with attention to the subtleties of the original Greek. These '
                 'original sources are frequently supplemented both by ancient art and by modern comparanda, '
                 'including opera and cinema (from Jacques Offenbach\u0027s opera Tales of Hoffman to Ridley '
                 'Scott\u0027s science fiction classic Blade Runner).</p>',
        'format': 'standard_html'
    },
    'field_course_start_date': '1363147200',
    'field_course_effort': '4-6 hours / week',
    'field_course_school_node': [
        {
            'uri': 'https://www.edx.org/node/242',
            'id': '242',
            'resource': 'node',
            'uuid': '44022f13-20df-4666-9111-cede3e5dc5b6'
        }
    ],
    'field_course_end_date': '1376971200',
    'field_course_video': [],
    'field_course_resources': [],
    'field_course_sub_title_long': {
        'value': '<p>A survey of ancient Greek literature focusing on classical concepts of the hero and how they '
                 'can inform our understanding of the human condition.</p>\n',
        'format': 'plain_text'
    },
    'field_course_subject': [
        {
            'uri': 'https://www.edx.org/node/652',
            'id': '652',
            'resource': 'node',
            'uuid': 'c8579e1c-99f2-4a95-988c-3542909f055e'
        },
        {
            'uri': 'https://www.edx.org/node/653',
            'id': '653',
            'resource': 'node',
            'uuid': '00e5d5e0-ce45-4114-84a1-50a5be706da5'
        },
        {
            'uri': 'https://www.edx.org/node/655',
            'id': '655',
            'resource': 'node',
            'uuid': '74b6ed2a-3ba0-49be-adc9-53f7256a12e1'
        }
    ],
    'field_course_statement_title': None,
    'field_course_statement_body': [],
    'field_course_status': 'past',
    'field_course_start_override': None,
    'field_course_email': None,
    'field_course_syllabus': [],
    'field_course_staff': [
        {
            'uri': 'https://www.edx.org/node/564',
            'id': '564',
            'resource': 'node',
            'uuid': 'ae56688a-f2b6-4981-9aa7-5c66b68cb13e'
        },
        {
            'uri': 'https://www.edx.org/node/565',
            'id': '565',
            'resource': 'node',
            'uuid': '56d13e72-353f-48fd-9be7-6f20ef467bb7'
        },
        {
            'uri': 'https://www.edx.org/node/566',
            'id': '566',
            'resource': 'node',
            'uuid': '69a415db-3db7-436a-8d02-e571c4c4c75a'
        },
        {
            'uri': 'https://www.edx.org/node/567',
            'id': '567',
            'resource': 'node',
            'uuid': '1639460f-598c-45b7-90c2-bbdbf87cdd54'
        },
        {
            'uri': 'https://www.edx.org/node/568',
            'id': '568',
            'resource': 'node',
            'uuid': '09154d2c-7f31-477c-9d3c-d8cba9af846e'
        },
        {
            'uri': 'https://www.edx.org/node/820',
            'id': '820',
            'resource': 'node',
            'uuid': '05b7ab45-de9a-49d6-8010-04c68fc9fd55'
        },
        {
            'uri': 'https://www.edx.org/node/821',
            'id': '821',
            'resource': 'node',
            'uuid': '8a8d68c4-ab5b-40c5-b897-2d44aed2194d'
        },
        {
            'uri': 'https://www.edx.org/node/822',
            'id': '822',
            'resource': 'node',
            'uuid': 'c3e16519-a23f-4f21-908b-463375b492df'
        }
    ],
    'field_course_staff_override': 'G. Nagy, L. Muellner...',
    'field_course_image_promoted': {
        'fid': '32381',
        'name': 'tombstone_courses.jpg',
        'mime': 'image/jpeg',
        'size': '34861',
        'url': 'https://www.edx.org/sites/default/files/course/image/promoted/tombstone_courses_ORIGINAL.jpg',
        'timestamp': '1384348699',
        'owner': {
            'uri': 'https://www.edx.org/user/1',
            'id': '1',
            'resource': 'user',
            'uuid': '434dea4f-7b93-4cba-9965-fe4856062a4f'
        },
        'uuid': '1471888c-a451-4f97-9bb2-ad20c9a43c2d'
    },
    'field_course_image_banner': {
        'fid': '32285',
        'name': 'cb22x_608x211.jpg',
        'mime': 'image/jpeg',
        'size': '25909',
        'url': 'https://www.edx.org/sites/default/files/course/image/banner/cb22x_608x211.jpg',
        'timestamp': '1384348498',
        'owner': {
            'uri': 'https://www.edx.org/user/1',
            'id': '1',
            'resource': 'user',
            'uuid': '434dea4f-7b93-4cba-9965-fe4856062a4f'
        },
        'uuid': '15022bf7-e367-4a5c-b115-3755016de286'
    },
    'field_course_image_tile': {
        'fid': '32475',
        'name': 'cb22x-listing-banner.jpg',
        'mime': 'image/jpeg',
        'size': '47678',
        'url': 'https://www.edx.org/sites/default/files/course/image/tile/cb22x-listing-banner.jpg',
        'timestamp': '1384348906',
        'owner': {
            'uri': 'https://www.edx.org/user/1',
            'id': '1',
            'resource': 'user',
            'uuid': '434dea4f-7b93-4cba-9965-fe4856062a4f'
        },
        'uuid': '71735cc4-7ac3-4065-ad92-6f18f979eb0e'
    },
    'field_course_image_video': {
        'fid': '32573',
        'name': 'h_no_video_320x211_1_0.jpg',
        'mime': 'image/jpeg',
        'size': '2829',
        'url': 'https://www.edx.org/sites/default/files/course/image/video/h_no_video_320x211_1_0.jpg',
        'timestamp': '1384349121',
        'owner': {
            'uri': 'https://www.edx.org/user/1',
            'id': '1',
            'resource': 'user',
            'uuid': '434dea4f-7b93-4cba-9965-fe4856062a4f'
        },
        'uuid': '4d18789f-0909-4289-9d58-2292e5d03aee'
    },
    'field_course_id': 'HarvardX/CB22x/2014_Spring',
    'field_course_image_sample_cert': [],
    'field_course_image_sample_thumb': [],
    'field_course_enrollment_audit': True,
    'field_course_enrollment_honor': False,
    'field_course_enrollment_verified': False,
    'field_course_xseries_enable': False,
    'field_course_statement_image': [],
    'field_course_image_card': [],
    'field_course_image_featured_card': [],
    'field_course_code_override': None,
    'field_course_video_link_mp4': [],
    'field_course_video_duration': None,
    'field_course_self_paced': True,
    'field_course_new': None,
    'field_course_registration_dates': {
        'value': '1384348442',
        'value2': None,
        'duration': None
    },
    'field_course_enrollment_prof_ed': None,
    'field_course_enrollment_ap_found': None,
    'field_cource_price': None,
    'field_course_additional_keywords': 'Free,',
    'field_course_enrollment_mobile': None,
    'field_course_part_of_products': [],
    'field_course_level': None,
    'field_course_what_u_will_learn': [],
    'field_course_video_locale_lang': [],
    'field_course_languages': [],
    'field_couse_is_hidden': None,
    'field_xseries_display_override': [],
    'field_course_extra_description': [],
    'field_course_extra_desc_title': None,
    'field_course_body': [],
    'field_course_enrollment_no_id': None,
    'field_course_has_prerequisites': True,
    'field_course_enrollment_credit': None,
    'field_course_is_disabled': None,
    'field_course_tags': STAGE_TAG_FIELD_RESPONSE_DATA,
    'field_course_sub_title_short': 'ORIGINAL A survey of ancient Greek literature focusing on classical concepts of'
                                    ' the hero and how they can inform our understanding of the human condition.',
    'field_course_length_weeks': '23 weeks',
    'field_course_start_date_style': None,
    'field_course_head_prom_bkg_color': None,
    'field_course_head_promo_image': [],
    'field_course_head_promo_text': [],
    'field_course_outcome': None,
    'field_course_required_weeks': None,
    'field_course_required_days': None,
    'field_course_required_hours': None,
    'nid': '563',
    'vid': '8080',
    'is_new': False,
    'type': 'course',
    'title': 'HarvardX: CB22x: The Ancient Greek Hero',
    'language': 'und',
    'url': 'https://www.edx.org/course/ancient-greek-hero-harvardx-cb22x',
    'edit_url': 'https://www.edx.org/node/563/edit',
    'status': '0',
    'promote': '0',
    'sticky': '0',
    'created': '1384348442',
    'changed': '1443028625',
    'author': {
        'uri': 'https://www.edx.org/user/143',
        'id': '143',
        'resource': 'user',
        'uuid': '8ed4adee-6f84-4bec-8b64-20f9bfe7af0c'
    },
    'log': 'Updated by FeedsNodeProcessor',
    'revision': None,
    'body': [],
    'uuid': '6b8b779f-f567-4e98-aa41-a265d6fa073d',
    'vuuid': 'e0f8c80a-b377-4546-b247-1c94ab3a218d'
}

UPDATED_MARKETING_SITE_API_COURSE_BODY = {
    'field_course_code': 'CB22x',
    'field_course_course_title': {
        'value': 'The Ancient Greek Hero UPDATED',
        'format': 'basic_html'
    },
    'field_course_description': {
        'value': 'UPDATED <p><b>NOTE ABOUT OUR START DATE:</b> Although the course was launched on March 13th, '
                 'it\u0027s not too late to start participating! New participants will be joining the course until '
                 '<strong>registration closes on July 11</strong>. We offer everyone a flexible schedule and '
                 'multiple paths for participation. You can work through the course videos and readings at your '
                 'own pace to complete the associated exercises <strong>by August 26</strong>, the official course '
                 'end date. Or, you may choose to \u0022audit\u0022 the course by exploring just the particular '
                 'videos and readings that seem most suited to your interests. You are free to do as much or as '
                 'little as you would like!</p>\n<h3>\n\tOverview</h3>\n<p>What is it to be human, and how can '
                 'ancient concepts of the heroic and anti-heroic inform our understanding of the human condition? '
                 'That question is at the core of The Ancient Greek Hero, which introduces (or reintroduces) '
                 'students to the great texts of classical Greek culture by focusing on concepts of the Hero in an '
                 'engaging, highly comparative way.</p>\n<p>The classical Greeks\u0027 concepts of Heroes and the '
                 '\u0022heroic\u0022 were very different from the way we understand the term today. In this '
                 'course, students analyze Greek heroes and anti-heroes in their own historical contexts, in order '
                 'to gain an understanding of these concepts as they were originally understood while also '
                 'learning how they can inform our understanding of the human condition in general.</p>\n<p>In '
                 'Greek tradition, a hero was a human, male or female, of the remote past, who was endowed with '
                 'superhuman abilities by virtue of being descended from an immortal god. Rather than being '
                 'paragons of virtue, as heroes are viewed in many modern cultures, ancient Greek heroes had all '
                 'of the qualities and faults of their fellow humans, but on a much larger scale. Further, despite '
                 'their mortality, heroes, like the gods, were objects of cult worship \u2013 a dimension which is '
                 'also explored in depth in the course.</p>\n<p>The original sources studied in this course include'
                 ' the Homeric Iliad and Odyssey; tragedies of Aeschylus, Sophocles, and Euripides; songs of Sappho'
                 ' and Pindar; dialogues of Plato; historical texts of Herodotus; and more, including the '
                 'intriguing but rarely studied dialogue \u0022On Heroes\u0022 by Philostratus. All works are '
                 'presented in English translation, with attention to the subtleties of the original Greek. These '
                 'original sources are frequently supplemented both by ancient art and by modern comparanda, '
                 'including opera and cinema (from Jacques Offenbach\u0027s opera Tales of Hoffman to Ridley '
                 'Scott\u0027s science fiction classic Blade Runner).</p>',
        'format': 'standard_html'
    },
    'field_course_start_date': '1363147200',
    'field_course_effort': '4-6 hours / week',
    'field_course_school_node': [
        {
            'uri': 'https://www.edx.org/node/242',
            'id': '242',
            'resource': 'node',
            'uuid': '44022f13-20df-4666-9111-cede3e5dc5b6'
        }
    ],
    'field_course_end_date': '1376971200',
    'field_course_video': [],
    'field_course_resources': [],
    'field_course_sub_title_long': {
        'value': '<p>A survey of ancient Greek literature focusing on classical concepts of the hero and how they '
                 'can inform our understanding of the human condition.</p>\n',
        'format': 'plain_text'
    },
    'field_course_subject': [
        {
            'uri': 'https://www.edx.org/node/652',
            'id': '652',
            'resource': 'node',
            'uuid': 'c8579e1c-99f2-4a95-988c-3542909f055e'
        },
        {
            'uri': 'https://www.edx.org/node/653',
            'id': '653',
            'resource': 'node',
            'uuid': '00e5d5e0-ce45-4114-84a1-50a5be706da5'
        },
        {
            'uri': 'https://www.edx.org/node/655',
            'id': '655',
            'resource': 'node',
            'uuid': '74b6ed2a-3ba0-49be-adc9-53f7256a12e1'
        }
    ],
    'field_course_statement_title': None,
    'field_course_statement_body': [],
    'field_course_status': 'past',
    'field_course_start_override': None,
    'field_course_email': None,
    'field_course_syllabus': [],
    'field_course_staff': [
        {
            'uri': 'https://www.edx.org/node/564',
            'id': '564',
            'resource': 'node',
            'uuid': 'ae56688a-f2b6-4981-9aa7-5c66b68cb13e'
        },
        {
            'uri': 'https://www.edx.org/node/565',
            'id': '565',
            'resource': 'node',
            'uuid': '56d13e72-353f-48fd-9be7-6f20ef467bb7'
        },
        {
            'uri': 'https://www.edx.org/node/566',
            'id': '566',
            'resource': 'node',
            'uuid': '69a415db-3db7-436a-8d02-e571c4c4c75a'
        },
        {
            'uri': 'https://www.edx.org/node/567',
            'id': '567',
            'resource': 'node',
            'uuid': '1639460f-598c-45b7-90c2-bbdbf87cdd54'
        },
        {
            'uri': 'https://www.edx.org/node/568',
            'id': '568',
            'resource': 'node',
            'uuid': '09154d2c-7f31-477c-9d3c-d8cba9af846e'
        },
        {
            'uri': 'https://www.edx.org/node/820',
            'id': '820',
            'resource': 'node',
            'uuid': '05b7ab45-de9a-49d6-8010-04c68fc9fd55'
        },
        {
            'uri': 'https://www.edx.org/node/821',
            'id': '821',
            'resource': 'node',
            'uuid': '8a8d68c4-ab5b-40c5-b897-2d44aed2194d'
        },
        {
            'uri': 'https://www.edx.org/node/822',
            'id': '822',
            'resource': 'node',
            'uuid': 'c3e16519-a23f-4f21-908b-463375b492df'
        }
    ],
    'field_course_staff_override': 'G. Nagy, L. Muellner...',
    'field_course_image_promoted': {
        'fid': '32381',
        'name': 'tombstone_courses.jpg',
        'mime': 'image/jpeg',
        'size': '34861',
        'url': 'https://www.edx.org/sites/default/files/course/image/promoted/tombstone_courses_UPDATED.jpg',
        'timestamp': '1384348699',
        'owner': {
            'uri': 'https://www.edx.org/user/1',
            'id': '1',
            'resource': 'user',
            'uuid': '434dea4f-7b93-4cba-9965-fe4856062a4f'
        },
        'uuid': '1471888c-a451-4f97-9bb2-ad20c9a43c2d'
    },
    'field_course_image_banner': {
        'fid': '32285',
        'name': 'cb22x_608x211.jpg',
        'mime': 'image/jpeg',
        'size': '25909',
        'url': 'https://www.edx.org/sites/default/files/course/image/banner/cb22x_608x211.jpg',
        'timestamp': '1384348498',
        'owner': {
            'uri': 'https://www.edx.org/user/1',
            'id': '1',
            'resource': 'user',
            'uuid': '434dea4f-7b93-4cba-9965-fe4856062a4f'
        },
        'uuid': '15022bf7-e367-4a5c-b115-3755016de286'
    },
    'field_course_image_tile': {
        'fid': '32475',
        'name': 'cb22x-listing-banner.jpg',
        'mime': 'image/jpeg',
        'size': '47678',
        'url': 'https://www.edx.org/sites/default/files/course/image/tile/cb22x-listing-banner.jpg',
        'timestamp': '1384348906',
        'owner': {
            'uri': 'https://www.edx.org/user/1',
            'id': '1',
            'resource': 'user',
            'uuid': '434dea4f-7b93-4cba-9965-fe4856062a4f'
        },
        'uuid': '71735cc4-7ac3-4065-ad92-6f18f979eb0e'
    },
    'field_course_image_video': {
        'fid': '32573',
        'name': 'h_no_video_320x211_1_0.jpg',
        'mime': 'image/jpeg',
        'size': '2829',
        'url': 'https://www.edx.org/sites/default/files/course/image/video/h_no_video_320x211_1_0.jpg',
        'timestamp': '1384349121',
        'owner': {
            'uri': 'https://www.edx.org/user/1',
            'id': '1',
            'resource': 'user',
            'uuid': '434dea4f-7b93-4cba-9965-fe4856062a4f'
        },
        'uuid': '4d18789f-0909-4289-9d58-2292e5d03aee'
    },
    'field_course_id': 'HarvardX/CB22x/2014_Spring',
    'field_course_image_sample_cert': [],
    'field_course_image_sample_thumb': [],
    'field_course_enrollment_audit': True,
    'field_course_enrollment_honor': False,
    'field_course_enrollment_verified': False,
    'field_course_xseries_enable': False,
    'field_course_statement_image': [],
    'field_course_image_card': [],
    'field_course_image_featured_card': [],
    'field_course_code_override': None,
    'field_course_video_link_mp4': [],
    'field_course_video_duration': None,
    'field_course_self_paced': True,
    'field_course_new': None,
    'field_course_registration_dates': {
        'value': '1384348442',
        'value2': None,
        'duration': None
    },
    'field_course_enrollment_prof_ed': None,
    'field_course_enrollment_ap_found': None,
    'field_cource_price': None,
    'field_course_additional_keywords': 'Free,',
    'field_course_enrollment_mobile': None,
    'field_course_part_of_products': [],
    'field_course_level': None,
    'field_course_what_u_will_learn': [],
    'field_course_video_locale_lang': [],
    'field_course_languages': [],
    'field_couse_is_hidden': None,
    'field_xseries_display_override': [],
    'field_course_extra_description': [],
    'field_course_extra_desc_title': None,
    'field_course_body': [],
    'field_course_enrollment_no_id': None,
    'field_course_has_prerequisites': True,
    'field_course_enrollment_credit': None,
    'field_course_is_disabled': None,
    'field_course_tags': STAGE_TAG_FIELD_RESPONSE_DATA,
    'field_course_sub_title_short': 'UPDATED A survey of ancient Greek literature focusing on classical concepts of'
                                    ' the hero and how they can inform our understanding of the human condition.',
    'field_course_length_weeks': '23 weeks',
    'field_course_start_date_style': None,
    'field_course_head_prom_bkg_color': None,
    'field_course_head_promo_image': [],
    'field_course_head_promo_text': [],
    'field_course_outcome': None,
    'field_course_required_weeks': None,
    'field_course_required_days': None,
    'field_course_required_hours': None,
    'nid': '563',
    'vid': '8080',
    'is_new': False,
    'type': 'course',
    'title': 'HarvardX: CB22x: The Ancient Greek Hero',
    'language': 'und',
    'url': 'https://www.edx.org/course/ancient-greek-hero-harvardx-cb22x',
    'edit_url': 'https://www.edx.org/node/563/edit',
    'status': '1',
    'promote': '0',
    'sticky': '0',
    'created': '1384348442',
    'changed': '1443028625',
    'author': {
        'uri': 'https://www.edx.org/user/143',
        'id': '143',
        'resource': 'user',
        'uuid': '8ed4adee-6f84-4bec-8b64-20f9bfe7af0c'
    },
    'log': 'Updated by FeedsNodeProcessor',
    'revision': None,
    'body': [],
    'uuid': '6b8b779f-f567-4e98-aa41-a265d6fa073d',
    'vuuid': 'e0f8c80a-b377-4546-b247-1c94ab3a218d'
}

NEW_RUN_MARKETING_SITE_API_COURSE_BODY = {
    'field_course_code': 'CB22x',
    'field_course_course_title': {
        'value': 'The Ancient Greek Hero NEW_RUN',
        'format': 'basic_html'
    },
    'field_course_description': {
        'value': 'NEW_RUN <p><b>NOTE ABOUT OUR START DATE:</b> Although the course was launched on March 13th, '
                 'it\u0027s not too late to start participating! New participants will be joining the course until '
                 '<strong>registration closes on July 11</strong>. We offer everyone a flexible schedule and '
                 'multiple paths for participation. You can work through the course videos and readings at your '
                 'own pace to complete the associated exercises <strong>by August 26</strong>, the official course '
                 'end date. Or, you may choose to \u0022audit\u0022 the course by exploring just the particular '
                 'videos and readings that seem most suited to your interests. You are free to do as much or as '
                 'little as you would like!</p>\n<h3>\n\tOverview</h3>\n<p>What is it to be human, and how can '
                 'ancient concepts of the heroic and anti-heroic inform our understanding of the human condition? '
                 'That question is at the core of The Ancient Greek Hero, which introduces (or reintroduces) '
                 'students to the great texts of classical Greek culture by focusing on concepts of the Hero in an '
                 'engaging, highly comparative way.</p>\n<p>The classical Greeks\u0027 concepts of Heroes and the '
                 '\u0022heroic\u0022 were very different from the way we understand the term today. In this '
                 'course, students analyze Greek heroes and anti-heroes in their own historical contexts, in order '
                 'to gain an understanding of these concepts as they were originally understood while also '
                 'learning how they can inform our understanding of the human condition in general.</p>\n<p>In '
                 'Greek tradition, a hero was a human, male or female, of the remote past, who was endowed with '
                 'superhuman abilities by virtue of being descended from an immortal god. Rather than being '
                 'paragons of virtue, as heroes are viewed in many modern cultures, ancient Greek heroes had all '
                 'of the qualities and faults of their fellow humans, but on a much larger scale. Further, despite '
                 'their mortality, heroes, like the gods, were objects of cult worship \u2013 a dimension which is '
                 'also explored in depth in the course.</p>\n<p>The original sources studied in this course include'
                 ' the Homeric Iliad and Odyssey; tragedies of Aeschylus, Sophocles, and Euripides; songs of Sappho'
                 ' and Pindar; dialogues of Plato; historical texts of Herodotus; and more, including the '
                 'intriguing but rarely studied dialogue \u0022On Heroes\u0022 by Philostratus. All works are '
                 'presented in English translation, with attention to the subtleties of the original Greek. These '
                 'original sources are frequently supplemented both by ancient art and by modern comparanda, '
                 'including opera and cinema (from Jacques Offenbach\u0027s opera Tales of Hoffman to Ridley '
                 'Scott\u0027s science fiction classic Blade Runner).</p>',
        'format': 'standard_html'
    },
    'field_course_start_date': '1363147200',
    'field_course_effort': '4-6 hours / week',
    'field_course_school_node': [
        {
            'uri': 'https://www.edx.org/node/242',
            'id': '242',
            'resource': 'node',
            'uuid': '44022f13-20df-4666-9111-cede3e5dc5b6'
        }
    ],
    'field_course_end_date': '1376971200',
    'field_course_video': [],
    'field_course_resources': [],
    'field_course_sub_title_long': {
        'value': '<p>A survey of ancient Greek literature focusing on classical concepts of the hero and how they '
                 'can inform our understanding of the human condition.</p>\n',
        'format': 'plain_text'
    },
    'field_course_subject': [
        {
            'uri': 'https://www.edx.org/node/652',
            'id': '652',
            'resource': 'node',
            'uuid': 'c8579e1c-99f2-4a95-988c-3542909f055e'
        },
        {
            'uri': 'https://www.edx.org/node/653',
            'id': '653',
            'resource': 'node',
            'uuid': '00e5d5e0-ce45-4114-84a1-50a5be706da5'
        },
        {
            'uri': 'https://www.edx.org/node/655',
            'id': '655',
            'resource': 'node',
            'uuid': '74b6ed2a-3ba0-49be-adc9-53f7256a12e1'
        }
    ],
    'field_course_statement_title': None,
    'field_course_statement_body': [],
    'field_course_status': 'past',
    'field_course_start_override': None,
    'field_course_email': None,
    'field_course_syllabus': [],
    'field_course_staff': [
        {
            'uri': 'https://www.edx.org/node/564',
            'id': '564',
            'resource': 'node',
            'uuid': 'ae56688a-f2b6-4981-9aa7-5c66b68cb13e'
        },
        {
            'uri': 'https://www.edx.org/node/565',
            'id': '565',
            'resource': 'node',
            'uuid': '56d13e72-353f-48fd-9be7-6f20ef467bb7'
        },
        {
            'uri': 'https://www.edx.org/node/566',
            'id': '566',
            'resource': 'node',
            'uuid': '69a415db-3db7-436a-8d02-e571c4c4c75a'
        },
        {
            'uri': 'https://www.edx.org/node/567',
            'id': '567',
            'resource': 'node',
            'uuid': '1639460f-598c-45b7-90c2-bbdbf87cdd54'
        },
        {
            'uri': 'https://www.edx.org/node/568',
            'id': '568',
            'resource': 'node',
            'uuid': '09154d2c-7f31-477c-9d3c-d8cba9af846e'
        },
        {
            'uri': 'https://www.edx.org/node/820',
            'id': '820',
            'resource': 'node',
            'uuid': '05b7ab45-de9a-49d6-8010-04c68fc9fd55'
        },
        {
            'uri': 'https://www.edx.org/node/821',
            'id': '821',
            'resource': 'node',
            'uuid': '8a8d68c4-ab5b-40c5-b897-2d44aed2194d'
        },
        {
            'uri': 'https://www.edx.org/node/822',
            'id': '822',
            'resource': 'node',
            'uuid': 'c3e16519-a23f-4f21-908b-463375b492df'
        }
    ],
    'field_course_staff_override': 'G. Nagy, L. Muellner...',
    'field_course_image_promoted': {
        'fid': '32381',
        'name': 'tombstone_courses.jpg',
        'mime': 'image/jpeg',
        'size': '34861',
        'url': 'https://www.edx.org/sites/default/files/course/image/promoted/tombstone_courses_NEW_RUN.jpg',
        'timestamp': '1384348699',
        'owner': {
            'uri': 'https://www.edx.org/user/1',
            'id': '1',
            'resource': 'user',
            'uuid': '434dea4f-7b93-4cba-9965-fe4856062a4f'
        },
        'uuid': '1471888c-a451-4f97-9bb2-ad20c9a43c2d'
    },
    'field_course_image_banner': {
        'fid': '32285',
        'name': 'cb22x_608x211.jpg',
        'mime': 'image/jpeg',
        'size': '25909',
        'url': 'https://www.edx.org/sites/default/files/course/image/banner/cb22x_608x211.jpg',
        'timestamp': '1384348498',
        'owner': {
            'uri': 'https://www.edx.org/user/1',
            'id': '1',
            'resource': 'user',
            'uuid': '434dea4f-7b93-4cba-9965-fe4856062a4f'
        },
        'uuid': '15022bf7-e367-4a5c-b115-3755016de286'
    },
    'field_course_image_tile': {
        'fid': '32475',
        'name': 'cb22x-listing-banner.jpg',
        'mime': 'image/jpeg',
        'size': '47678',
        'url': 'https://www.edx.org/sites/default/files/course/image/tile/cb22x-listing-banner.jpg',
        'timestamp': '1384348906',
        'owner': {
            'uri': 'https://www.edx.org/user/1',
            'id': '1',
            'resource': 'user',
            'uuid': '434dea4f-7b93-4cba-9965-fe4856062a4f'
        },
        'uuid': '71735cc4-7ac3-4065-ad92-6f18f979eb0e'
    },
    'field_course_image_video': {
        'fid': '32573',
        'name': 'h_no_video_320x211_1_0.jpg',
        'mime': 'image/jpeg',
        'size': '2829',
        'url': 'https://www.edx.org/sites/default/files/course/image/video/h_no_video_320x211_1_0.jpg',
        'timestamp': '1384349121',
        'owner': {
            'uri': 'https://www.edx.org/user/1',
            'id': '1',
            'resource': 'user',
            'uuid': '434dea4f-7b93-4cba-9965-fe4856062a4f'
        },
        'uuid': '4d18789f-0909-4289-9d58-2292e5d03aee'
    },
    'field_course_id': 'HarvardX/CB22x/2016_Spring',
    'field_course_image_sample_cert': [],
    'field_course_image_sample_thumb': [],
    'field_course_enrollment_audit': True,
    'field_course_enrollment_honor': False,
    'field_course_enrollment_verified': False,
    'field_course_xseries_enable': False,
    'field_course_statement_image': [],
    'field_course_image_card': [],
    'field_course_image_featured_card': [],
    'field_course_code_override': None,
    'field_course_video_link_mp4': [],
    'field_course_video_duration': None,
    'field_course_self_paced': True,
    'field_course_new': None,
    'field_course_registration_dates': {
        'value': '1384348442',
        'value2': None,
        'duration': None
    },
    'field_course_enrollment_prof_ed': None,
    'field_course_enrollment_ap_found': None,
    'field_cource_price': None,
    'field_course_additional_keywords': 'Free,',
    'field_course_enrollment_mobile': None,
    'field_course_part_of_products': [],
    'field_course_level': None,
    'field_course_what_u_will_learn': [],
    'field_course_video_locale_lang': [],
    'field_course_languages': [],
    'field_couse_is_hidden': None,
    'field_xseries_display_override': [],
    'field_course_extra_description': [],
    'field_course_extra_desc_title': None,
    'field_course_body': [],
    'field_course_enrollment_no_id': None,
    'field_course_has_prerequisites': True,
    'field_course_enrollment_credit': None,
    'field_course_is_disabled': None,
    'field_course_tags': STAGE_TAG_FIELD_RESPONSE_DATA,
    'field_course_sub_title_short': 'NEW_RUN A survey of ancient Greek literature focusing on classical concepts of'
                                    ' the hero and how they can inform our understanding of the human condition.',
    'field_course_length_weeks': '23 weeks',
    'field_course_start_date_style': None,
    'field_course_head_prom_bkg_color': None,
    'field_course_head_promo_image': [],
    'field_course_head_promo_text': [],
    'field_course_outcome': None,
    'field_course_required_weeks': None,
    'field_course_required_days': None,
    'field_course_required_hours': None,
    'nid': '563',
    'vid': '8080',
    'is_new': False,
    'type': 'course',
    'title': 'HarvardX: CB22x: The Ancient Greek Hero',
    'language': 'und',
    'url': 'https://www.edx.org/course/ancient-greek-hero-harvardx-cb22x',
    'edit_url': 'https://www.edx.org/node/563/edit',
    'status': '1',
    'promote': '0',
    'sticky': '0',
    'created': '1384348442',
    'changed': '1443028625',
    'author': {
        'uri': 'https://www.edx.org/user/143',
        'id': '143',
        'resource': 'user',
        'uuid': '8ed4adee-6f84-4bec-8b64-20f9bfe7af0c'
    },
    'log': 'Updated by FeedsNodeProcessor',
    'revision': None,
    'body': [],
    'uuid': '6b8b779f-f567-4e98-aa41-a265d6fa073a',
    'vuuid': 'e0f8c80a-b377-4546-b247-1c94ab3a218a'
}


DISCOVERY_CREATED_MARKETING_SITE_API_COURSE_BODY = {
    'field_course_uuid': 'f0f8c80a-b377-4546-b547-1c94ab3a218a',
    'field_course_code': 'CB22x',
    'field_course_course_title': {
        'value': 'The Ancient Greek Hero DISCOVERY_CREATED',
        'format': 'basic_html'
    },
    'field_course_description': {
        'value': 'DISCOVERY_CREATED <p><b>NOTE ABOUT OUR START DATE:</b> Although the course was launched,'
                 'it\u0027s not too late to start participating! New participants will be joining the course until '
                 '<strong>registration closes on July 11</strong>. We offer everyone a flexible schedule and '
                 'multiple paths for participation. You can work through the course videos and readings at your '
                 'own pace to complete the associated exercises <strong>by August 26</strong>, the official course '
                 'end date. Or, you may choose to \u0022audit\u0022 the course by exploring just the particular '
                 'videos and readings that seem most suited to your interests. You are free to do as much or as '
                 'little as you would like!</p>\n<h3>\n\tOverview</h3>\n<p>What is it to be human, and how can '
                 'ancient concepts of the heroic and anti-heroic inform our understanding of the human condition? '
                 'That question is at the core of The Ancient Greek Hero, which introduces (or reintroduces) '
                 'students to the great texts of classical Greek culture by focusing on concepts of the Hero in an '
                 'engaging, highly comparative way.</p>\n<p>The classical Greeks\u0027 concepts of Heroes and the '
                 '\u0022heroic\u0022 were very different from the way we understand the term today. In this '
                 'course, students analyze Greek heroes and anti-heroes in their own historical contexts, in order '
                 'to gain an understanding of these concepts as they were originally understood while also '
                 'learning how they can inform our understanding of the human condition in general.</p>\n<p>In '
                 'Greek tradition, a hero was a human, male or female, of the remote past, who was endowed with '
                 'superhuman abilities by virtue of being descended from an immortal god. Rather than being '
                 'paragons of virtue, as heroes are viewed in many modern cultures, ancient Greek heroes had all '
                 'of the qualities and faults of their fellow humans, but on a much larger scale. Further, despite '
                 'their mortality, heroes, like the gods, were objects of cult worship \u2013 a dimension which is '
                 'also explored in depth in the course.</p>\n<p>The original sources studied in this course include'
                 ' the Homeric Iliad and Odyssey; tragedies of Aeschylus, Sophocles, and Euripides; songs of Sappho'
                 ' and Pindar; dialogues of Plato; historical texts of Herodotus; and more, including the '
                 'intriguing but rarely studied dialogue \u0022On Heroes\u0022 by Philostratus. All works are '
                 'presented in English translation, with attention to the subtleties of the original Greek. These '
                 'original sources are frequently supplemented both by ancient art and by modern comparanda, '
                 'including opera and cinema (from Jacques Offenbach\u0027s opera Tales of Hoffman to Ridley '
                 'Scott\u0027s science fiction classic Blade Runner).</p>',
        'format': 'standard_html'
    },
    'field_course_start_date': '1363147200',
    'field_course_effort': '4-6 hours / week',
    'field_course_school_node': [
        {
            'uri': 'https://www.edx.org/node/242',
            'id': '242',
            'resource': 'node',
            'uuid': '44022f13-20df-4666-9111-cede3e5dc5b6'
        }
    ],
    'field_course_end_date': '1376971200',
    'field_course_video': [],
    'field_course_resources': [],
    'field_course_sub_title_long': {
        'value': '<p>A survey of ancient Greek literature focusing on classical concepts of the hero and how they '
                 'can inform our understanding of the human condition.</p>\n',
        'format': 'plain_text'
    },
    'field_course_subject': [
        {
            'uri': 'https://www.edx.org/node/652',
            'id': '652',
            'resource': 'node',
            'uuid': 'c8579e1c-99f2-4a95-988c-3542909f055e'
        },
        {
            'uri': 'https://www.edx.org/node/653',
            'id': '653',
            'resource': 'node',
            'uuid': '00e5d5e0-ce45-4114-84a1-50a5be706da5'
        },
        {
            'uri': 'https://www.edx.org/node/655',
            'id': '655',
            'resource': 'node',
            'uuid': '74b6ed2a-3ba0-49be-adc9-53f7256a12e1'
        }
    ],
    'field_course_statement_title': None,
    'field_course_statement_body': [],
    'field_course_status': 'past',
    'field_course_start_override': None,
    'field_course_email': None,
    'field_course_syllabus': [],
    'field_course_staff': [
        {
            'uri': 'https://www.edx.org/node/564',
            'id': '564',
            'resource': 'node',
            'uuid': 'ae56688a-f2b6-4981-9aa7-5c66b68cb13e'
        },
        {
            'uri': 'https://www.edx.org/node/565',
            'id': '565',
            'resource': 'node',
            'uuid': '56d13e72-353f-48fd-9be7-6f20ef467bb7'
        },
        {
            'uri': 'https://www.edx.org/node/566',
            'id': '566',
            'resource': 'node',
            'uuid': '69a415db-3db7-436a-8d02-e571c4c4c75a'
        },
        {
            'uri': 'https://www.edx.org/node/567',
            'id': '567',
            'resource': 'node',
            'uuid': '1639460f-598c-45b7-90c2-bbdbf87cdd54'
        },
        {
            'uri': 'https://www.edx.org/node/568',
            'id': '568',
            'resource': 'node',
            'uuid': '09154d2c-7f31-477c-9d3c-d8cba9af846e'
        },
        {
            'uri': 'https://www.edx.org/node/820',
            'id': '820',
            'resource': 'node',
            'uuid': '05b7ab45-de9a-49d6-8010-04c68fc9fd55'
        },
        {
            'uri': 'https://www.edx.org/node/821',
            'id': '821',
            'resource': 'node',
            'uuid': '8a8d68c4-ab5b-40c5-b897-2d44aed2194d'
        },
        {
            'uri': 'https://www.edx.org/node/822',
            'id': '822',
            'resource': 'node',
            'uuid': 'c3e16519-a23f-4f21-908b-463375b492df'
        }
    ],
    'field_course_staff_override': 'G. Nagy, L. Muellner...',
    'field_course_image_promoted': {
        'fid': '32381',
        'name': 'tombstone_courses.jpg',
        'mime': 'image/jpeg',
        'size': '34861',
        'url': 'https://www.edx.org/sites/default/files/course/image/promoted/tombstone_courses_NEW_RUN.jpg',
        'timestamp': '1384348699',
        'owner': {
            'uri': 'https://www.edx.org/user/1',
            'id': '1',
            'resource': 'user',
            'uuid': '434dea4f-7b93-4cba-9965-fe4856062a4f'
        },
        'uuid': '1471888c-a451-4f97-9bb2-ad20c9a43c2d'
    },
    'field_course_image_banner': {
        'fid': '32285',
        'name': 'cb22x_608x211.jpg',
        'mime': 'image/jpeg',
        'size': '25909',
        'url': 'https://www.edx.org/sites/default/files/course/image/banner/cb22x_608x211.jpg',
        'timestamp': '1384348498',
        'owner': {
            'uri': 'https://www.edx.org/user/1',
            'id': '1',
            'resource': 'user',
            'uuid': '434dea4f-7b93-4cba-9965-fe4856062a4f'
        },
        'uuid': '15022bf7-e367-4a5c-b115-3755016de286'
    },
    'field_course_image_tile': {
        'fid': '32475',
        'name': 'cb22x-listing-banner.jpg',
        'mime': 'image/jpeg',
        'size': '47678',
        'url': 'https://www.edx.org/sites/default/files/course/image/tile/cb22x-listing-banner.jpg',
        'timestamp': '1384348906',
        'owner': {
            'uri': 'https://www.edx.org/user/1',
            'id': '1',
            'resource': 'user',
            'uuid': '434dea4f-7b93-4cba-9965-fe4856062a4f'
        },
        'uuid': '71735cc4-7ac3-4065-ad92-6f18f979eb0e'
    },
    'field_course_image_video': {
        'fid': '32573',
        'name': 'h_no_video_320x211_1_0.jpg',
        'mime': 'image/jpeg',
        'size': '2829',
        'url': 'https://www.edx.org/sites/default/files/course/image/video/h_no_video_320x211_1_0.jpg',
        'timestamp': '1384349121',
        'owner': {
            'uri': 'https://www.edx.org/user/1',
            'id': '1',
            'resource': 'user',
            'uuid': '434dea4f-7b93-4cba-9965-fe4856062a4f'
        },
        'uuid': '4d18789f-0909-4289-9d58-2292e5d03aee'
    },
    'field_course_id': 'HarvardX/CB22x/2016_Spring',
    'field_course_image_sample_cert': [],
    'field_course_image_sample_thumb': [],
    'field_course_enrollment_audit': True,
    'field_course_enrollment_honor': False,
    'field_course_enrollment_verified': False,
    'field_course_xseries_enable': False,
    'field_course_statement_image': [],
    'field_course_image_card': [],
    'field_course_image_featured_card': [],
    'field_course_code_override': None,
    'field_course_video_link_mp4': [],
    'field_course_video_duration': None,
    'field_course_self_paced': True,
    'field_course_new': None,
    'field_course_registration_dates': {
        'value': '1384348442',
        'value2': None,
        'duration': None
    },
    'field_course_enrollment_prof_ed': None,
    'field_course_enrollment_ap_found': None,
    'field_cource_price': None,
    'field_course_additional_keywords': 'Free,',
    'field_course_enrollment_mobile': None,
    'field_course_part_of_products': [],
    'field_course_level': None,
    'field_course_what_u_will_learn': [],
    'field_course_video_locale_lang': [],
    'field_course_languages': [],
    'field_couse_is_hidden': None,
    'field_xseries_display_override': [],
    'field_course_extra_description': [],
    'field_course_extra_desc_title': None,
    'field_course_body': [],
    'field_course_enrollment_no_id': None,
    'field_course_has_prerequisites': True,
    'field_course_enrollment_credit': None,
    'field_course_is_disabled': None,
    'field_course_tags': STAGE_TAG_FIELD_RESPONSE_DATA,
    'field_course_sub_title_short': 'NEW_RUN A survey of ancient Greek literature focusing on classical concepts of'
                                    ' the hero and how they can inform our understanding of the human condition.',
    'field_course_length_weeks': '23 weeks',
    'field_course_start_date_style': None,
    'field_course_head_prom_bkg_color': None,
    'field_course_head_promo_image': [],
    'field_course_head_promo_text': [],
    'field_course_outcome': None,
    'field_course_required_weeks': None,
    'field_course_required_days': None,
    'field_course_required_hours': None,
    'nid': '563',
    'vid': '8080',
    'is_new': False,
    'type': 'course',
    'title': 'HarvardX: CB22x: The Ancient Greek Hero',
    'language': 'und',
    'url': 'https://www.edx.org/course/ancient-greek-hero-harvardx-cb22x',
    'edit_url': 'https://www.edx.org/node/563/edit',
    'status': '1',
    'promote': '0',
    'sticky': '0',
    'created': '1384348442',
    'changed': '1443028625',
    'author': {
        'uri': 'https://www.edx.org/user/143',
        'id': '143',
        'resource': 'user',
        'uuid': '8ed4adee-6f84-4bec-8b64-20f9bfe7af0c'
    },
    'log': 'Updated by FeedsNodeProcessor',
    'revision': None,
    'body': [],
    'uuid': '6b8b779f-f567-4e98-aa41-a265d6fa073a',
    'vuuid': 'e0f8c80a-b377-4546-b247-1c94ab3a218a'
}
