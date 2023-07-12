# pylint: disable=line-too-long
"""
Mock data for testing purposes of Contentful Bootcamp Data transformation utils.
"""
import random
import string

from contentful import Entry


def create_contentful_entry(entry_name, fields):
    return Entry({
        'metadata': {'tags': []},
        'sys': {
            'space': {'sys': {'type': 'Link', 'linkType': 'Space', 'id': 'test_space_id'}},
            'id': ''.join(random.choices(string.ascii_letters + string.digits, k=22)),
            'type': 'Entry',
            'createdAt': '2022-12-05T21:20:18.606Z',
            'updatedAt': '2022-12-05T21:20:18.606Z',
            'environment': {'sys': {'id': 'master', 'type': 'Link', 'linkType': 'Environment'}},
            'revision': 1,
            'contentType': {
                'sys': {'type': 'Link', 'linkType': 'ContentType', 'id': entry_name}},
            'locale': 'en-US'
        },
        'fields': fields
    })


class MockContenfulDegreeResponse:
    """
    Mock Contentful Degree Response
    """

    degree_transformed_data = None
    mock_contentful_degree_entry = None

    def __init__(self, uuid):
        seo_entry = create_contentful_entry('seo', {
            'pageTitle': 'SEO Page Title',
            'pageDescription': 'SEO Page Description',
            'languageCode': 'en'
        })
        hero_entry = create_contentful_entry('hero', {
            'internalName': 'Hero Internal Name',
            'subheading': 'Hero Sub-heading',
            'textList': {'nodeType': 'document', 'data': {}, 'content': [{'nodeType': 'unordered-list', 'data': {}, 'content': [{'nodeType': 'list-item', 'data': {}, 'content': [{'nodeType': 'paragraph', 'data': {}, 'content': [{'value': 'Lorem ipsum:', 'nodeType': 'text', 'marks': [{'type': 'bold'}], 'data': {}}, {'value': ' dolor sit amet, consectetur adipiscing elit', 'nodeType': 'text', 'marks': [], 'data': {}}]}]}, {'nodeType': 'list-item', 'data': {}, 'content': [{'nodeType': 'paragraph', 'data': {}, 'content': [{'value': 'Lorem ipsum:', 'nodeType': 'text', 'marks': [{'type': 'bold'}], 'data': {}}, {'value': ' dolor sit amet, consectetur adipiscing elit', 'nodeType': 'text', 'marks': [], 'data': {}}]}]}, {'nodeType': 'list-item', 'data': {}, 'content': [{'nodeType': 'paragraph', 'data': {}, 'content': [{'value': 'Lorem ipsum:', 'nodeType': 'text', 'marks': [{'type': 'bold'}], 'data': {}}, {'value': ' dolor sit amet, consectetur adipiscing elit', 'nodeType': 'text', 'marks': [], 'data': {}}]}]}, {'nodeType': 'list-item', 'data': {}, 'content': [{'nodeType': 'paragraph', 'data': {}, 'content': [{'value': 'Lorem ipsum:', 'nodeType': 'text', 'marks': [{'type': 'bold'}], 'data': {}}, {'value': ' dolor sit amet, consectetur adipiscing elit', 'nodeType': 'text', 'marks': [], 'data': {}}]}]}]}]},
        })
        about_the_program_entry = create_contentful_entry('aboutTheProgramModule', {
            'internalName': 'About program internal name',
            'heading': 'About program heading',
            'content': {'nodeType': 'document', 'data': {}, 'content': [{'nodeType': 'paragraph', 'data': {}, 'content': [{'value': 'Lorem ipsum dolor sit amet, consectetur adipiscing elit', 'nodeType': 'text', 'marks': [], 'data': {}}]}]},
            'checkmarkedItems': create_contentful_entry('textListModule', {
                'title': 'About program check-marked title',
                'theme': 'background-white',
                'textListItems': [create_contentful_entry('textListItem', {
                    'header': 'About program check-marked text list header',
                    'description': {'nodeType': 'document', 'data': {}, 'content': [{'nodeType': 'paragraph', 'data': {}, 'content': [{'value': 'Lorem ipsum:', 'nodeType': 'text', 'marks': [{'type': 'bold'}], 'data': {}}, {'value': ' dolor sit amet, consectetur adipiscing elit', 'nodeType': 'text', 'marks': [], 'data': {}}]}]}
                })]
            }),
        })
        placement_about_section_entry = create_contentful_entry('placementAboutSection', {
            'internalName': 'Placement about internal name',
            'heading': 'Placement about heading',
            'bodyText': {'nodeType': 'document', 'data': {}, 'content': [{'nodeType': 'paragraph', 'data': {}, 'content': [{'value': 'Lorem ipsum:', 'nodeType': 'text', 'marks': [{'type': 'bold'}], 'data': {}}, {'value': ' dolor sit amet, consectetur adipiscing elit', 'nodeType': 'text', 'marks': [], 'data': {}}]}]}
        })
        featured_products_entry = create_contentful_entry('featuredProductsModule', {
            'internalName': 'Featured product internal name',
            'heading': 'Featured product heading',
            'introduction': 'Featured product introduction',
            'introRichText': {'nodeType': 'document', 'data': {}, 'content': [{'nodeType': 'paragraph', 'data': {}, 'content': [{'value': 'Rich Text 1', 'nodeType': 'text', 'marks': [{'type': 'bold'}], 'data': {}}, {'value': ' Rich Text 2', 'nodeType': 'text', 'marks': [], 'data': {}}]}]},
            'productList': create_contentful_entry('textListModule', {
                'title': 'Featured product list title',
                'theme': 'background-white',
                'textListItems': [create_contentful_entry('textListItem', {
                    'header': 'Featured product list text header',
                    'description': {'nodeType': 'document', 'data': {}, 'content': [{'nodeType': 'paragraph', 'data': {}, 'content': [{'value': 'Lorem ipsum:', 'nodeType': 'text', 'marks': [{'type': 'bold'}], 'data': {}}, {'value': ' dolor sit amet, consectetur adipiscing elit', 'nodeType': 'text', 'marks': [], 'data': {}}]}]}
                })]
            }),
        })
        featured_products_entry__missing_rich_text = create_contentful_entry('featuredProductsModule', {
            'internalName': 'Featured product internal name',
            'heading': 'Featured product heading',
            'introduction': 'Featured product introduction',
            'productList': create_contentful_entry('textListModule', {
                'title': 'Featured product list title',
                'theme': 'background-white',
                'textListItems': [create_contentful_entry('textListItem', {
                    'header': 'Featured product list text header',
                    'description': {'nodeType': 'document', 'data': {}, 'content': [
                        {'nodeType': 'paragraph', 'data': {}, 'content': [
                            {'value': 'Lorem ipsum:', 'nodeType': 'text', 'marks': [{'type': 'bold'}], 'data': {}},
                            {'value': ' dolor sit amet, consectetur adipiscing elit', 'nodeType': 'text', 'marks': [],
                             'data': {}}]}]}
                })]
            }),
        })

        faq_entry = create_contentful_entry('faqModule', {
            'name': 'FAQ Module Name',
            'faqs': [
                create_contentful_entry('faq', {
                    'name': 'faq name',
                    'question': 'faq question',
                    'answerRichText': {'nodeType': 'document', 'data': {}, 'content': [{'nodeType': 'paragraph', 'data': {}, 'content': [{'value': 'Lorem ipsum dolor sit amet, consectetur adipiscing elit', 'nodeType': 'text', 'marks': [], 'data': {}}]}, {'nodeType': 'paragraph', 'data': {}, 'content': [{'value': 'Lorem ipsum dolor sit amet, consectetur adipiscing elit', 'nodeType': 'text', 'marks': [{'type': 'bold'}], 'data': {}}]}, {'nodeType': 'unordered-list', 'data': {}, 'content': [{'nodeType': 'list-item', 'data': {}, 'content': [{'nodeType': 'paragraph', 'data': {}, 'content': [{'value': 'Lorem ipsum dolor sit amet, consectetur adipiscing elit', 'nodeType': 'text', 'marks': [], 'data': {}}]}]}, {'nodeType': 'list-item', 'data': {}, 'content': [{'nodeType': 'paragraph', 'data': {}, 'content': [{'value': 'Lorem ipsum dolor sit amet, consectetur adipiscing elit', 'nodeType': 'text', 'marks': [], 'data': {}}]}]}, {'nodeType': 'list-item', 'data': {}, 'content': [{'nodeType': 'paragraph', 'data': {}, 'content': [{'value': 'Lorem ipsum dolor sit amet, consectetur adipiscing elit', 'nodeType': 'text', 'marks': [], 'data': {}}]}]}, {'nodeType': 'list-item', 'data': {}, 'content': [{'nodeType': 'paragraph', 'data': {}, 'content': [{'value': 'Lorem ipsum dolor sit amet, consectetur adipiscing elit', 'nodeType': 'text', 'marks': [], 'data': {}}]}]}]}]}
                })
            ]
        })

        degree_contentful_entry = {
            'internalName': 'Lorem ipsum dolor sit amet, consectetur adipiscing elit',
            'uuid_list': ['test-uuid1', 'test-uuid2', 'test-uuid3'],
            'excluded_from_search': False,
            'excluded_from_seo': False,
            'seo': seo_entry,
            'hero': hero_entry,
            'modules': [
                about_the_program_entry,
                faq_entry,
                placement_about_section_entry,
                featured_products_entry
            ]
        }

        if uuid:
            degree_contentful_entry['uuid'] = uuid

        self.mock_contentful_degree_entry = create_contentful_entry('degreeDetailPage', degree_contentful_entry)

        degree_contentful_entry['modules'] = [
            about_the_program_entry,
            faq_entry,
            placement_about_section_entry,
            featured_products_entry__missing_rich_text
        ]

        self.mock_contentful_degree_missing_rich_text = create_contentful_entry(
            'degreeDetailPage', degree_contentful_entry)

        self.degree_sample_contentful_entry = {
            'page_title': 'SEO Page Title',
            'subheading': 'Hero Sub-heading',
            'excluded_from_search': False,
            'excluded_from_seo': False,
            'about_the_program': {
                'heading': 'About program heading',
                'content': 'Lorem ipsum dolor sit amet, consectetur adipiscing elit',
                'checkmarked_items': ['Lorem ipsum: dolor sit amet, consectetur adipiscing elit']
            },
            'featured_products': {
                'heading': 'Featured product heading',
                'introduction': 'Rich Text 1 Rich Text 2',
                'product_list': [{
                    'header': 'Featured product list text header',
                    'description': 'Lorem ipsum: dolor sit amet, consectetur adipiscing elit'
                }]
            },
            'placement_about_section': {
                'heading': 'Placement about heading',
                'body_text': 'Lorem ipsum: dolor sit amet, consectetur adipiscing elit'
            },
            'faq_items': [{
                'question': 'faq question',
                'answer': 'Lorem ipsum dolor sit amet, consectetur adipiscing elit Lorem ipsum dolor sit amet,'
                          ' consectetur adipiscing elit Lorem ipsum dolor sit amet, consectetur adipiscing elit'
                          ' Lorem ipsum dolor sit amet, consectetur adipiscing elit Lorem ipsum dolor sit amet,'
                          ' consectetur adipiscing elit Lorem ipsum dolor sit amet, consectetur adipiscing elit'
            }]
        }

        self.degree_transformed_data = {
            'test-uuid1': self.degree_sample_contentful_entry,
            'test-uuid2': self.degree_sample_contentful_entry,
            'test-uuid3': self.degree_sample_contentful_entry
        }

        if uuid:
            self.degree_transformed_data[uuid] = self.degree_sample_contentful_entry


def create_bootcamp_mock_response_data():
    """
    Creates bootcamp mock response data.
    """
    seo_entry = create_contentful_entry('seo', {
        'pageTitle': 'Lorem ipsum dolor sit amet, consectetur adipiscing elit',
        'pageDescription': 'Lorem ipsum dolor sit amet, consectetur adipiscing elit',
        'languageCode': 'en'
    })

    hero_entry = create_contentful_entry('hero', {
        'internalName': 'Lorem ipsum dolor sit amet, consectetur adipiscing elit',
        'subheading': 'Lorem ipsum dolor sit amet, consectetur adipiscing elit',
        'textList': {'nodeType': 'document', 'data': {}, 'content': [{'nodeType': 'unordered-list', 'data': {}, 'content': [{'nodeType': 'list-item', 'data': {}, 'content': [{'nodeType': 'paragraph', 'data': {}, 'content': [{'value': 'Lorem ipsum:', 'nodeType': 'text', 'marks': [{'type': 'bold'}], 'data': {}}, {'value': ' dolor sit amet, consectetur adipiscing elit', 'nodeType': 'text', 'marks': [], 'data': {}}]}]}, {'nodeType': 'list-item', 'data': {}, 'content': [{'nodeType': 'paragraph', 'data': {}, 'content': [{'value': 'Lorem ipsum:', 'nodeType': 'text', 'marks': [{'type': 'bold'}], 'data': {}}, {'value': ' dolor sit amet, consectetur adipiscing elit', 'nodeType': 'text', 'marks': [], 'data': {}}]}]}, {'nodeType': 'list-item', 'data': {}, 'content': [{'nodeType': 'paragraph', 'data': {}, 'content': [{'value': 'Lorem ipsum:', 'nodeType': 'text', 'marks': [{'type': 'bold'}], 'data': {}}, {'value': ' dolor sit amet, consectetur adipiscing elit', 'nodeType': 'text', 'marks': [], 'data': {}}]}]}, {'nodeType': 'list-item', 'data': {}, 'content': [{'nodeType': 'paragraph', 'data': {}, 'content': [{'value': 'Lorem ipsum:', 'nodeType': 'text', 'marks': [{'type': 'bold'}], 'data': {}}, {'value': ' dolor sit amet, consectetur adipiscing elit', 'nodeType': 'text', 'marks': [], 'data': {}}]}]}]}]},
    })

    about_the_program_entry = create_contentful_entry('aboutTheProgramModule', {
        'internalName': 'Lorem ipsum dolor sit amet, consectetur adipiscing elit',
        'heading': 'Lorem ipsum dolor sit amet, consectetur adipiscing elit',
        'content': {'nodeType': 'document', 'data': {}, 'content': [{'nodeType': 'paragraph', 'data': {}, 'content': [{'value': 'Lorem ipsum dolor sit amet, consectetur adipiscing elit', 'nodeType': 'text', 'marks': [], 'data': {}}]}]},
        'checkmarkedItems': create_contentful_entry('textListModule', {
            'title': 'Lorem ipsum dolor sit amet, consectetur adipiscing elit',
            'theme': 'background-white',
            'textListItems': [create_contentful_entry('textListItem', {
                   'header': 'Lorem ipsum dolor sit amet, consectetur adipiscing elit',
                   'description': {'nodeType': 'document', 'data': {}, 'content': [{'nodeType': 'paragraph', 'data': {}, 'content': [{'value': 'Lorem ipsum:', 'nodeType': 'text', 'marks': [{'type': 'bold'}], 'data': {}}, {'value': ' dolor sit amet, consectetur adipiscing elit', 'nodeType': 'text', 'marks': [], 'data': {}}]}]}
            })]
        }),
    })

    blurb1_entry = create_contentful_entry('blurbModule', {
        'internalName': 'Lorem ipsum dolor sit amet, consectetur adipiscing elit',
        'blurbHeading': 'Lorem ipsum dolor sit amet, consectetur adipiscing elit',
        'blurbBody': {'nodeType': 'document', 'data': {}, 'content': [{'nodeType': 'heading-3', 'data': {}, 'content': [{'value': 'Lorem ipsum dolor sit amet, consectetur adipiscing elit', 'nodeType': 'text', 'marks': [], 'data': {}}]}, {'nodeType': 'paragraph', 'data': {}, 'content': [{'value': 'Lorem ipsum dolor sit amet, consectetur adipiscing elit', 'nodeType': 'text', 'marks': [], 'data': {}}]}, {'nodeType': 'heading-3', 'data': {}, 'content': [{'value': 'Lorem ipsum dolor sit amet, consectetur adipiscing elit', 'nodeType': 'text', 'marks': [], 'data': {}}]}, {'nodeType': 'paragraph', 'data': {}, 'content': [{'value': 'Lorem ipsum dolor sit amet, consectetur adipiscing elit', 'nodeType': 'text', 'marks': [], 'data': {}}, {'nodeType': 'embedded-entry-inline', 'content': []}]}, {'nodeType': 'paragraph', 'data': {}, 'content': [{'value': 'Lorem ipsum dolor sit amet, consectetur adipiscing elit', 'nodeType': 'text', 'marks': [], 'data': {}}, {'nodeType': 'embedded-entry-inline', 'content': []}]}, {'nodeType': 'heading-3', 'data': {}, 'content': [{'value': 'Lorem ipsum dolor sit amet, consectetur adipiscing elit', 'nodeType': 'text', 'marks': [], 'data': {}}]}, {'nodeType': 'paragraph', 'data': {}, 'content': [{'value': 'Lorem ipsum dolor sit amet, consectetur adipiscing elit', 'nodeType': 'text', 'marks': [], 'data': {}}]}]}
    })

    bootcamp_curriculum_entry = create_contentful_entry('bootCampCurriculumModule', {
        'internalName': 'Lorem ipsum dolor sit amet, consectetur adipiscing elit',
        'subheading': {'nodeType': 'document', 'data': {}, 'content': [{'nodeType': 'heading-3', 'data': {}, 'content': [{'value': 'Lorem ipsum dolor sit amet, consectetur adipiscing elit', 'nodeType': 'text', 'marks': [], 'data': {}}]}, {'nodeType': 'paragraph', 'data': {}, 'content': [{'value': 'Lorem ipsum dolor sit amet, consectetur adipiscing elit', 'nodeType': 'text', 'marks': [], 'data': {}}, {'value': 'Lorem ipsum dolor sit amet, consectetur adipiscing elit', 'nodeType': 'text', 'marks': [{'type': 'bold'}], 'data': {}}, {'value': 'Lorem ipsum dolor sit amet, consectetur adipiscing elit', 'nodeType': 'text', 'marks': [], 'data': {}}, {'value': 'Lorem ipsum dolor sit amet, consectetur adipiscing elit', 'nodeType': 'text', 'marks': [], 'data': {}}, {'value': 'Lorem ipsum dolor sit amet, consectetur adipiscing elit', 'nodeType': 'text', 'marks': [{'type': 'bold'}], 'data': {}}, {'value': 'Lorem ipsum dolor sit amet, consectetur adipiscing elit', 'nodeType': 'text', 'marks': [], 'data': {}}]}]},
        'items': [create_contentful_entry('faq', {
            'name': 'Lorem ipsum dolor sit amet, consectetur adipiscing elit',
            'question': 'Lorem ipsum dolor sit amet, consectetur adipiscing elit',
            'answerRichText': {'nodeType': 'document', 'data': {}, 'content': [{'nodeType': 'paragraph', 'data': {}, 'content': [{'value': 'Lorem ipsum dolor sit amet, consectetur adipiscing elit', 'nodeType': 'text', 'marks': [], 'data': {}}]}, {'nodeType': 'paragraph', 'data': {}, 'content': [{'value': 'Lorem ipsum dolor sit amet, consectetur adipiscing elit', 'nodeType': 'text', 'marks': [{'type': 'bold'}], 'data': {}}]}, {'nodeType': 'unordered-list', 'data': {}, 'content': [{'nodeType': 'list-item', 'data': {}, 'content': [{'nodeType': 'paragraph', 'data': {}, 'content': [{'value': 'Lorem ipsum dolor sit amet, consectetur adipiscing elit', 'nodeType': 'text', 'marks': [], 'data': {}}]}]}, {'nodeType': 'list-item', 'data': {}, 'content': [{'nodeType': 'paragraph', 'data': {}, 'content': [{'value': 'Lorem ipsum dolor sit amet, consectetur adipiscing elit', 'nodeType': 'text', 'marks': [], 'data': {}}]}]}, {'nodeType': 'list-item', 'data': {}, 'content': [{'nodeType': 'paragraph', 'data': {}, 'content': [{'value': 'Lorem ipsum dolor sit amet, consectetur adipiscing elit', 'nodeType': 'text', 'marks': [], 'data': {}}]}]}, {'nodeType': 'list-item', 'data': {}, 'content': [{'nodeType': 'paragraph', 'data': {}, 'content': [{'value': 'Lorem ipsum dolor sit amet, consectetur adipiscing elit', 'nodeType': 'text', 'marks': [], 'data': {}}]}]}]}]}
        })]
    })

    partnership_entry = create_contentful_entry('partnershipModule', {
        'internalName': 'Lorem ipsum dolor sit amet, consectetur adipiscing elit',
        'headingText': {'nodeType': 'document', 'data': {}, 'content': [{'nodeType': 'paragraph', 'data': {}, 'content': [{'value': 'Lorem ipsum dolor sit amet, consectetur adipiscing elit', 'nodeType': 'text', 'marks': [], 'data': {}}]}]},
        'bodyText': {'nodeType': 'document', 'data': {}, 'content': [{'nodeType': 'paragraph', 'data': {}, 'content': [{'value': 'Lorem ipsum dolor sit amet, consectetur adipiscing elit', 'nodeType': 'text', 'marks': [], 'data': {}}, {'value': 'Lorem', 'nodeType': 'text', 'marks': [{'type': 'bold'}], 'data': {}}, {'value': ', ', 'nodeType': 'text', 'marks': [], 'data': {}}, {'value': 'ipsum', 'nodeType': 'text', 'marks': [{'type': 'bold'}], 'data': {}}, {'value': ', or ', 'nodeType': 'text', 'marks': [], 'data': {}}, {'value': 'dolor', 'nodeType': 'text', 'marks': [{'type': 'bold'}], 'data': {}}, {'value': 'Lorem ipsum dolor sit amet, consectetur adipiscing elit', 'nodeType': 'text', 'marks': [], 'data': {}}]}]},
    })

    blurb2_entry = create_contentful_entry('blurbModule', {
        'internalName': 'Lorem ipsum dolor sit amet, consectetur adipiscing elit',
        'blurbHeading': 'Lorem ipsum dolor sit amet, consectetur adipiscing elit',
        'blurbBody': {'nodeType': 'document', 'data': {}, 'content': [{'nodeType': 'heading-3', 'data': {}, 'content': [{'value': 'Lorem ipsum dolor sit amet, consectetur adipiscing elit', 'nodeType': 'text', 'marks': [], 'data': {}}]}, {'nodeType': 'paragraph', 'data': {}, 'content': [{'value': 'Lorem ipsum dolor sit amet, consectetur adipiscing elit', 'nodeType': 'text', 'marks': [], 'data': {}}]}, {'nodeType': 'paragraph', 'data': {}, 'content': [{'value': 'Lorem ipsum dolor sit amet, consectetur adipiscing elit', 'nodeType': 'text', 'marks': [], 'data': {}}]}]}
    })

    faq_entry = create_contentful_entry('faqModule', {
        'name': 'Lorem ipsum dolor sit amet, consectetur adipiscing elit',
        'faqs': [
            create_contentful_entry('faq', {
                'name': 'Lorem ipsum dolor sit amet, consectetur adipiscing elit',
                'question': 'Lorem ipsum dolor sit amet, consectetur adipiscing elit',
                'answerRichText': {'nodeType': 'document', 'data': {}, 'content': [{'nodeType': 'paragraph', 'data': {}, 'content': [{'value': 'Lorem ipsum dolor sit amet, consectetur adipiscing elit', 'nodeType': 'text', 'marks': [], 'data': {}}]}, {'nodeType': 'paragraph', 'data': {}, 'content': [{'value': 'Lorem ipsum dolor sit amet, consectetur adipiscing elit', 'nodeType': 'text', 'marks': [{'type': 'bold'}], 'data': {}}]}, {'nodeType': 'unordered-list', 'data': {}, 'content': [{'nodeType': 'list-item', 'data': {}, 'content': [{'nodeType': 'paragraph', 'data': {}, 'content': [{'value': 'Lorem ipsum dolor sit amet, consectetur adipiscing elit', 'nodeType': 'text', 'marks': [], 'data': {}}]}]}, {'nodeType': 'list-item', 'data': {}, 'content': [{'nodeType': 'paragraph', 'data': {}, 'content': [{'value': 'Lorem ipsum dolor sit amet, consectetur adipiscing elit', 'nodeType': 'text', 'marks': [], 'data': {}}]}]}, {'nodeType': 'list-item', 'data': {}, 'content': [{'nodeType': 'paragraph', 'data': {}, 'content': [{'value': 'Lorem ipsum dolor sit amet, consectetur adipiscing elit', 'nodeType': 'text', 'marks': [], 'data': {}}]}]}, {'nodeType': 'list-item', 'data': {}, 'content': [{'nodeType': 'paragraph', 'data': {}, 'content': [{'value': 'Lorem ipsum dolor sit amet, consectetur adipiscing elit', 'nodeType': 'text', 'marks': [], 'data': {}}]}]}]}]}
            })
        ]
    })

    return create_contentful_entry('bootCampPage', {
        'internalName': 'Lorem ipsum dolor sit amet, consectetur adipiscing elit',
        'uuid': 'test-uuid',
        'excluded_from_search': False,
        'excluded_from_seo': False,
        'seo': seo_entry,
        'hero': hero_entry,
        'modules': [
            about_the_program_entry,
            blurb1_entry,
            bootcamp_curriculum_entry,
            partnership_entry,
            blurb2_entry,
            faq_entry,
        ]
    })


class MockContentfulBootcampResponse:
    """
    Mock response received from Contentful for bootcamp
    """
    total = 15
    items = [create_bootcamp_mock_response_data()]

    def __init__(self):
        self.mock_contentful_bootcamp_entry = self.items[0]
        self.bootcamp_transformed_data = {
            'test-uuid': {
                'page_title': 'Lorem ipsum dolor sit amet, consectetur adipiscing elit',
                'subheading': 'Lorem ipsum dolor sit amet, consectetur adipiscing elit',
                'excluded_from_search': False,
                'excluded_from_seo': False,
                'hero_text_list': 'Lorem ipsum: dolor sit amet, consectetur adipiscing elit Lorem ipsum: dolor sit '
                                  'amet, consectetur adipiscing elit Lorem ipsum: dolor sit amet, consectetur '
                                  'adipiscing elit Lorem ipsum: dolor sit amet, consectetur adipiscing elit',
                'about_the_program': {
                    'heading': 'Lorem ipsum dolor sit amet, consectetur adipiscing elit',
                    'content': 'Lorem ipsum dolor sit amet, consectetur adipiscing elit',
                    'checkmarked_items': ['Lorem ipsum: dolor sit amet, consectetur adipiscing elit']
                },
                'blurb_1': {
                    'heading': 'Lorem ipsum dolor sit amet, consectetur adipiscing elit',
                    'body': 'Lorem ipsum dolor sit amet, consectetur adipiscing elit Lorem ipsum dolor sit amet,'
                            ' consectetur adipiscing elit Lorem ipsum dolor sit amet, consectetur adipiscing elit'
                            ' Lorem ipsum dolor sit amet, consectetur adipiscing elit Lorem ipsum dolor sit amet,'
                            ' consectetur adipiscing elit Lorem ipsum dolor sit amet, consectetur adipiscing elit'
                            ' Lorem ipsum dolor sit amet, consectetur adipiscing elit'
                },
                'blurb_2': {
                    'heading': 'Lorem ipsum dolor sit amet, consectetur adipiscing elit',
                    'body': 'Lorem ipsum dolor sit amet, consectetur adipiscing elit Lorem ipsum dolor sit amet,'
                            ' consectetur adipiscing elit Lorem ipsum dolor sit amet, consectetur adipiscing elit'
                }, 'bootcamp_curriculum': {
                    'heading': 'Lorem ipsum dolor sit amet, consectetur adipiscing elit Lorem ipsum dolor sit amet,'
                               ' consectetur adipiscing elit Lorem ipsum dolor sit amet, consectetur adipiscing elit'
                               ' Lorem ipsum dolor sit amet, consectetur adipiscing elit Lorem ipsum dolor sit amet,'
                               ' consectetur adipiscing elit Lorem ipsum dolor sit amet, consectetur adipiscing elit'
                               ' Lorem ipsum dolor sit amet, consectetur adipiscing elit'
                }, 'partnerships': {
                    'heading_text': 'Lorem ipsum dolor sit amet, consectetur adipiscing elit',
                    'body_text': 'Lorem ipsum dolor sit amet, consectetur adipiscing elit Lorem , ipsum , or dolor'
                                 ' Lorem ipsum dolor sit amet, consectetur adipiscing elit'
                }, 'faq_items': [
                    {
                        'question': 'Lorem ipsum dolor sit amet, consectetur adipiscing elit',
                        'answer': 'Lorem ipsum dolor sit amet, consectetur adipiscing elit Lorem ipsum dolor sit amet,'
                                  ' consectetur adipiscing elit Lorem ipsum dolor sit amet, consectetur adipiscing elit'
                                  ' Lorem ipsum dolor sit amet, consectetur adipiscing elit Lorem ipsum dolor sit amet,'
                                  ' consectetur adipiscing elit Lorem ipsum dolor sit amet, consectetur adipiscing elit'
                    },
                    {
                        'question': 'Lorem ipsum dolor sit amet, consectetur adipiscing elit',
                        'answer': 'Lorem ipsum dolor sit amet, consectetur adipiscing elit Lorem ipsum dolor sit amet,'
                                  ' consectetur adipiscing elit Lorem ipsum dolor sit amet, consectetur adipiscing elit'
                                  ' Lorem ipsum dolor sit amet, consectetur adipiscing elit Lorem ipsum dolor sit amet,'
                                  ' consectetur adipiscing elit Lorem ipsum dolor sit amet, consectetur adipiscing elit'
                    }
                ]
            }
        }
