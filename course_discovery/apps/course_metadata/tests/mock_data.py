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

                'nid': '637',
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
        'type': 'subject',
        'title': 'Math',
        'url': 'https://www.edx.org/course/subject/math',
        'uuid': 'a669e004-cbc0-4b68-8882-234c12e1cce4',
    },
]

MARKETING_SITE_API_SCHOOL_BODIES = [
    {
        'field_school_description': {
            'value': '\u003Cp\u003EHarvard University is devoted to excellence in teaching, learning, and '
                     'research, and to developing leaders in many disciplines who make a difference globally. '
                     'Harvard faculty are engaged with teaching and research to push the boundaries of human '
                     'knowledge. The University has twelve degree-granting Schools in addition to the Radcliffe '
                     'Institute for Advanced Study.\u003C/p\u003E\n\n\u003Cp\u003EEstablished in 1636, Harvard '
                     'is the oldest institution of higher education in the United States. The University, which '
                     'is based in Cambridge and Boston, Massachusetts, has an enrollment of over 20,000 degree '
                     'candidates, including undergraduate, graduate, and professional students. Harvard has more '
                     'than 360,000 alumni around the world.\u003C/p\u003E',
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
            'value': '\u003Cp\u003EMassachusetts Institute of Technology \u2014 a coeducational, privately '
                     'endowed research university founded in 1861 \u2014 is dedicated to advancing knowledge '
                     'and educating students in science, technology, and other areas of scholarship that will '
                     'best serve the nation and the world in the 21st century. \u003Ca href=\u0022http://web.'
                     'mit.edu/aboutmit/\u0022 target=\u0022_blank\u0022\u003ELearn more about MIT\u003C/a\u003E'
                     '. Through MITx, the Institute furthers its commitment to improving education worldwide.'
                     '\u003C/p\u003E\n\n\u003Cp\u003E\u003Cstrong\u003EMITx Courses\u003C/strong\u003E\u003Cbr '
                     '/\u003E\nMITx courses embody the inventiveness, openness, rigor and quality that are '
                     'hallmarks of MIT, and many use materials developed for MIT residential courses in the '
                     'Institute\u0027s five schools and 33 academic disciplines. Browse MITx courses below.'
                     '\u003C/p\u003E\n\n\u003Cp\u003E\u00a0\u003C/p\u003E',
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

MARKETING_SITE_API_PERSON_BODIES = [
    {
        'field_person_first_middle_name': 'Michael',
        'field_person_last_name': 'Cima',
        'field_person_honorifics': None,
        'field_person_salutation': None,
        'field_person_position': None,
        'field_person_role': '1',
        'field_person_resume': {
            'value': '\u003Cp\u003EProf. Cima has been a faculty member at MIT for 29 years. He earned a B.S. in '
                     'chemistry and a Ph.D. in chemical engineering, both from the University of California at '
                     'Berkeley. He was elected a Fellow of the American Ceramics Society in 1997 and was elected to '
                     'the National Academy of Engineering in 2011. Prof. Cima\u0027s research concerns advanced '
                     'technology for medical devices that are used for drug delivery and diagnostics, high-throughput '
                     'development methods for formulations of materials and pharmaceutical formulations. Prof. Cima '
                     'is an author of over 250 publications and fifty US patents, a co-inventor of MIT\u2019s '
                     'three-dimensional printing process, and a co-founder of four companies.\u003C/p\u003E',
            'format': 'standard_html'
        },
        'field_person_image': {
            'url': 'https://www.edx.org/sites/default/files/person/image/professor-cima.11a117198ae0.jpg',
        },
        'field_person_areas_of_expertise': [],
        'field_person_major_works': [],
        'field_person_positions': [
            {
                'field_person_position_tiltes': [
                    'Faculty'
                ],
                'field_person_position_org_link': {
                    'title': 'MIT',
                    'url': 'https://www.edx.org/school/mitx'
                },
                'item_id': '11961',
                'revision_id': '29431',
                'field_name': 'field_person_positions',
                'archived': '0',
                'uuid': '796ec296-d08b-44a0-b817-09692ef815a5',
                'url': 'https://www.edx.org/field-collection/field-person-positions/11961',
            }
        ],
        'field_person_social_links': [
            {
                'field_person_social_link': {
                    'title': 'Website',
                    'url': 'http://ki.mit.edu/people/faculty/cima'
                },
                'field_person_social_link_type': 'generic',
                'item_id': '5711',
                'revision_id': '7761',
                'field_name': 'field_person_social_links',
                'archived': '0',
                'uuid': 'da41b1e9-da0b-49e3-b207-f619f166b0e8',
                'url': 'https://www.edx.org/field-collection/field-person-social-links/5711',
            }
        ],
        'type': 'person',
        'title': 'Michael Cima',
        'url': 'https://www.edx.org/bio/michael-cima',
        'uuid': '9569e046-e090-40ca-afb0-96b0a68cba31',
    },
    {
        'field_person_first_middle_name': 'Anant',
        'field_person_last_name': 'Agarwal',
        'field_person_honorifics': None,
        'field_person_salutation': None,
        'field_person_position': None,
        'field_person_role': '1',
        'field_person_resume': {
            'value': '\u003Cp\u003ECEO of edX and Professor of Electrical Engineering and Computer Science at MIT. '
                     'His research focus is in parallel computer architectures and cloud software systems, and he is '
                     'a founder of several successful startups, including Tilera, a company that produces scalable '
                     'multicore processors. Prof. Agarwal won MIT\u2019s Smullin and Jamieson prizes for teaching and '
                     'co-authored the course textbook \u201cFoundations of Analog and Digital Electronic Circuits.'
                     '\u201d\u003C/p\u003E',
            'format': 'standard_html'
        },
        'field_person_image': {
            'url': 'https://www.edx.org/sites/default/files/person/image/agarwal-small.b3b3a106003d.jpg',
        },
        'field_person_areas_of_expertise': [],
        'field_person_major_works': [],
        'field_person_positions': [
            {
                'field_person_position_tiltes': [
                    'CEO'
                ],
                'field_person_position_org_link': {
                    'title': 'edX',
                    'url': 'http://www.edx.org'
                },
                'item_id': '11966',
                'revision_id': '29436',
                'field_name': 'field_person_positions',
                'archived': '0',
                'uuid': '0601fd65-7a53-4552-b061-8082bccde4c3',
                'url': 'https://www.edx.org/field-collection/field-person-positions/11966',
            },
            {
                'field_person_position_tiltes': [
                    'Professor, Electrical Engineering and Computer Science'
                ],
                'field_person_position_org_link': {
                    'title': 'MIT',
                    'url': 'http://www.edx.org/school/mitx'
                },
                'item_id': '11971',
                'revision_id': '29441',
                'field_name': 'field_person_positions',
                'archived': '0',
                'uuid': 'cfc7f5f7-9668-474e-8349-e4e21c468da3',
                'url': 'https://www.edx.org/field-collection/field-person-positions/11971',
            }
        ],
        'field_person_social_links': [
            {
                'field_person_social_link': [],
                'field_person_social_link_type': 'generic',
                'item_id': '11976',
                'revision_id': '29446',
                'field_name': 'field_person_social_links',
                'archived': '0',
                'uuid': 'd22f1705-71b2-4644-95c8-afea9277ea6c',
                'url': 'https://www.edx.org/field-collection/field-person-social-links/11976',
            }
        ],
        'type': 'person',
        'title': 'Anant Agarwal',
        'url': 'https://www.edx.org/bio/anant-agarwal-0',
        'uuid': '352ea90b-7b9a-49a2-ba4f-165cbf6a3636',
    },
    {
        'field_person_first_middle_name': 'No',
        'field_person_last_name': 'Position',
        'field_person_honorifics': None,
        'field_person_salutation': None,
        'field_person_position': None,
        'field_person_role': '1',
        'field_person_resume': {
            'value': '',
        },
        'field_person_image': {
            'url': 'https://www.edx.org/sites/default/files/person/image/positionless.jpg',
        },
        'field_person_areas_of_expertise': [],
        'field_person_major_works': [],
        'field_person_positions': [],
        'type': 'person',
        'title': 'Positionless',
        'url': 'https://www.edx.org/bio/positionless',
        'uuid': '352ea90b-7b9a-49a2-ba4f-abccbf6a3636',
    },
    {
        'field_person_first_middle_name': 'No',
        'field_person_last_name': 'Title',
        'field_person_honorifics': None,
        'field_person_salutation': None,
        'field_person_position': None,
        'field_person_role': '1',
        'field_person_resume': {
            'value': '',
        },
        'field_person_image': {
            'url': 'https://www.edx.org/sites/default/files/person/image/titleless.jpg',
        },
        'field_person_areas_of_expertise': [],
        'field_person_major_works': [],
        'field_person_positions': [
            {
                'field_person_position_tiltes': [],
                'field_person_position_org_link': {
                    'title': 'edX',
                    'url': 'http://www.edx.org'
                },
            }
        ],
        'type': 'person',
        'title': 'Positionless',
        'url': 'https://www.edx.org/bio/titleless',
        'uuid': '352ea90b-7b9a-abc2-ba4f-165cbf6a3636',
    },
    {
        'field_person_first_middle_name': 'No',
        'field_person_last_name': 'Org',
        'field_person_honorifics': None,
        'field_person_salutation': None,
        'field_person_position': None,
        'field_person_role': '1',
        'field_person_resume': {
            'value': '',
        },
        'field_person_image': {
            'url': 'https://www.edx.org/sites/default/files/person/image/orgless.jpg',
        },
        'field_person_areas_of_expertise': [],
        'field_person_major_works': [],
        'field_person_positions': [
            {
                'field_person_position_tiltes': [
                    'CEO'
                ],
                'field_person_position_org_link': []
            }
        ],
        'type': 'person',
        'title': 'Orgless',
        'url': 'https://www.edx.org/bio/orgless',
        'uuid': 'abcea90b-7b9a-49a2-ba4f-165cbf6a3636',
    }
]
