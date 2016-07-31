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

MARKETING_SITE_API_XSERIES_BODIES = [
    {
        'field_course_effort': 'self-paced: 3 hours per week',
        'body': {
            'value': '<p>The Astrophysics XSeries Program consists of four foundational courses in astrophysics taught '
                     'by prestigious leaders in the field, including Nobel Prize winners.  You will be taught by Brian '
                     'Schmidt, who led the team that discovered dark energy – work which won him the 2011 Nobel Prize '
                     'for Physics, and by prize-winning educator, science communicator and astrophysics researcher '
                     'Paul Francis, who will take you through an incredible journey where you learn about the unsolved '
                     'mysteries of the universe, exoplanets, black holes and supernovae, and general cosmology. '
                     'Astronomy and astrophysics is the study of everything beyond Earth. Astronomers work in '
                     'universities, at observatories, for various space agencies like NASA, and more. The study of '
                     'astronomy provides you with a wide range of skills in math, engineering, and computation which '
                     'are sought after skills across many occupations. This XSeries Program is great for anyone to '
                     'start their studies in astronomy and astrophysics or individuals simply interested in what lies '
                     'beyond Earth.</p>',
            'summary': '',
            'format': 'standard_html'
        },
        'field_xseries_banner_image': {
            'fid': '65336',
            'name': 'aat075a_72.jpg',
            'mime': 'image/jpeg',
            'size': '146765',
            'url': 'https://stage.edx.org/sites/default/files/xseries/image/banner/aat075a_72.jpg',
            'timestamp': '1438027131',
            'owner': {
                'uri': 'https://stage.edx.org/user/9761',
                'id': '9761',
                'resource': 'user',
                'uuid': '4af80bce-a315-4ea2-8eb2-a65d03014673'
            },
            'uuid': 'd2a87930-2d6a-4f2b-867b-8711d981404a'
        },
        'field_course_level': 'Intermediate',
        'field_xseries_institutions': [
            {
                'field_school_description': {
                    'value': '<p>The Australian National University (ANU) is a celebrated place of intensive '
                             'research, education and policy engagement. Our research has always been central to '
                             'everything we do, shaping a holistic learning experience that goes beyond the classroom, '
                             'giving students access to researchers who are among the best in their fields and to '
                             'opportunities for development around Australia and the world.</p>',
                    'format': 'standard_html'
                },
                'field_school_name': 'Australian National University',
                'field_school_image_banner': {
                    'fid': '31524',
                    'name': 'anu-home-banner.jpg',
                    'mime': 'image/jpeg',
                    'size': '30181',
                    'url': 'https://stage.edx.org/sites/default/files/school/image/banner/anu-home-banner_0.jpg',
                    'timestamp': '1384283150',
                    'owner': {
                        'uri': 'https://stage.edx.org/user/1',
                        'id': '1',
                        'resource': 'user',
                        'uuid': '434dea4f-7b93-4cba-9965-fe4856062a4f'
                    },
                    'uuid': 'f7fca9c1-078b-45bd-b4c9-ae5a927ba632'
                },
                'field_school_image_logo': {
                    'fid': '31526',
                    'name': 'anu_logo_200x101.png',
                    'mime': 'image/png',
                    'size': '13977',
                    'url': 'https://stage.edx.org/sites/default/files/school/image/banner/anu_logo_200x101_0.png',
                    'timestamp': '1384283150',
                    'owner': {
                        'uri': 'https://stage.edx.org/user/1',
                        'id': '1',
                        'resource': 'user',
                        'uuid': '434dea4f-7b93-4cba-9965-fe4856062a4f'
                    },
                    'uuid': '74a40d7e-e81f-4de0-9733-04ca12d25605'
                },
                'field_school_image_logo_thumb': {
                    'fid': '31525',
                    'name': 'anu_logo_185x48.png',
                    'mime': 'image/png',
                    'size': '2732',
                    'url': 'https://stage.edx.org/sites/default/files/school/image/banner/anu_logo_185x48_0.png',
                    'timestamp': '1384283150',
                    'owner': {
                        'uri': 'https://stage.edx.org/user/1',
                        'id': '1',
                        'resource': 'user',
                        'uuid': '434dea4f-7b93-4cba-9965-fe4856062a4f'
                    },
                    'uuid': '14fbc10e-c6a8-499f-a53c-032f92c9da32'
                },
                'field_school_image_logo_sub': {
                    'fid': '31527',
                    'name': 'anu-on-edx-logo.png',
                    'mime': 'image/png',
                    'size': '4517',
                    'url': 'https://stage.edx.org/sites/default/files/school/image/banner/anu-on-edx-logo_0.png',
                    'timestamp': '1384283150',
                    'owner': {
                        'uri': 'https://stage.edx.org/user/1',
                        'id': '1',
                        'resource': 'user',
                        'uuid': '434dea4f-7b93-4cba-9965-fe4856062a4f'
                    },
                    'uuid': 'ea74abe3-66ce-48ba-bf6d-34b2e109fbeb'
                },
                'field_school_description_private': [],
                'field_school_subdomain_prefix': None,
                'field_school_url_slug': 'anux',
                'field_school_is_school': True,
                'field_school_is_partner': False,
                'field_school_is_contributor': True,
                'field_school_is_charter': True,
                'field_school_is_founder': False,
                'field_school_is_display': True,
                'field_school_freeform': [],
                'field_school_is_affiliate': False,
                'field_school_display_name': None,
                'field_school_catalog_heading': None,
                'field_school_catalog_subheading': None,
                'field_school_subtitle': None,
                'nid': '635',
                'vid': '7917',
                'is_new': False,
                'type': 'school',
                'title': 'ANUx',
                'language': 'und',
                'url': 'https://stage.edx.org/school/anux',
                'edit_url': 'https://stage.edx.org/node/635/edit',
                'status': '1',
                'promote': '0',
                'sticky': '0',
                'created': '1384283059',
                'changed': '1426706369',
                'author': {
                    'uri': 'https://stage.edx.org/user/143',
                    'id': '143',
                    'resource': 'user',
                    'uuid': '8ed4adee-6f84-4bec-8b64-20f9bfe7af0c'
                },
                'log': 'Updated by FeedsNodeProcessor',
                'revision': None,
                'body': [],
                'uuid': '1e6df8ed-a3fe-4307-99b9-775af509fcba',
                'vuuid': '98f08316-2d87-4412-8e03-838fa94a7f03'
            }
        ],
        'field_card_image': {
            'fid': '65346',
            'name': 'anu_astrophys_xseries_card.jpg',
            'mime': 'image/jpeg',
            'size': '53246',
            'url': 'https://stage.edx.org/sites/default/files/card/images/anu_astrophys_xseries_card.jpg',
            'timestamp': '1438043010',
            'owner': {
                'uri': 'https://stage.edx.org/user/9761',
                'id': '9761',
                'resource': 'user',
                'uuid': '4af80bce-a315-4ea2-8eb2-a65d03014673'
            },
            'uuid': '820b05ad-1283-47ab-a123-6a7a17868a37'
        },
        'field_xseries_length': 'self-paced: ~9 weeks per course',
        'field_xseries_overview': {
            'value': '<h3>What You\'ll Learn</h3> <ul><li>An understanding of the biggest unsolved mysteries in '
                     'astrophysics and how researchers are attempting to answer them</li> <li>Methods used to find '
                     'and study exoplanets</li> <li>How scientists tackle challenging problems</li> <li>About white '
                     'dwarfs, novae, supernovae, neutro stars and black holes and how quantum mechanics and relativity '
                     'help explain these objects</li> <li>How astrophysicists investigate the origin, nature and fate '
                     'of our universe</li> </ul>',
            'format': 'expanded_html'
        },
        'field_xseries_price': '$50/Course',
        'field_xseries_subtitle': 'Learn contemporary astrophysics from the leaders in the field.',
        'field_xseries_subtitle_short': 'Learn contemporary astrophysics from the leaders in the field.',
        'field_xseries_outcome': None,
        'field_xseries_required_weeks': None,
        'field_xseries_required_hours': None,
        'nid': '7046',
        'vid': '130386',
        'type': 'xseries',
        'title': 'Astrophysics',
        'language': 'und',
        'url': 'https://stage.edx.org/xseries/astrophysics'
    },
    {
        'body': {
            'value': '<p>In this XSeries, you will find all of the content required to be successful on the AP '
                     'Biology exam including genetics, the cell, ecology, diversity and evolution. You will also '
                     'find practice AP-style multiple choice and free response questions, tutorials on how to '
                     'formulate great responses and lab experiences that will be crucial to your success on the AP '
                     'exam.<br />  </p> <p><span>This XSeries consists of 5 courses.</span> The cost is $25 per '
                     'course. The total cost of this XSeries is $125. The component courses for this XSeries may be '
                     'taken individually.</p>',
            'summary': '',
            'format': 'standard_html'
        },
        'field_xseries_banner_image': {
            'url': 'https://stage.edx.org/sites/default/files/xseries/image/banner/ap-biology-exam.jpg'
        },
        'field_xseries_subtitle_short': 'Learn Biology!',
        'type': 'xseries',
        'title': 'Biology',
        'url': 'https://stage.edx.org/xseries/biology'
    },
]
