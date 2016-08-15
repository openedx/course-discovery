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
            },
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
            },
            'image': {
                'raw': 'http://example.com/image.jpg',
            },

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
            'url': 'https://prod-edx-mktg-edit.edx.org/sites/default/files/cs-1440x210.jpg'
        },
        'field_subject_url_slug': 'computer-science',
        'field_subject_subtitle': {
            'value': 'Learn about computer science from the best universities and institutions around the world.',
            'format': 'basic_html'
        },
        'field_subject_card_image': {
            'url': 'https://prod-edx-mktg-edit.edx.org/sites/default/files/subject/image/card/computer-science.jpg',
        },
        'type': 'subject',
        'title': 'Computer Science',
        'url': 'https://prod-edx-mktg-edit.edx.org/course/subject/math',
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
            'url': 'https://prod-edx-mktg-edit.edx.org/sites/default/files/mathemagical-1440x210.jpg',
        },
        'field_subject_url_slug': 'math',
        'field_subject_subtitle': {
            'value': 'Learn about math and more from the best universities and institutions around the world.',
            'format': 'basic_html'
        },
        'field_subject_card_image': {
            'url': 'https://prod-edx-mktg-edit.edx.org/sites/default/files/subject/image/card/math.jpg',
        },
        'type': 'subject',
        'title': 'Math',
        'url': 'https://prod-edx-mktg-edit.edx.org/course/subject/math',
        'uuid': 'a669e004-cbc0-4b68-8882-234c12e1cce4',
    },
]
