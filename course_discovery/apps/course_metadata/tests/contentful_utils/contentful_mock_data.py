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

    def __init__(self):
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
        placement_about_section_entry = create_contentful_entry('placementAboutSection', {
            'internalName': 'Lorem ipsum dolor sit amet, consectetur adipiscing elit',
            'heading': 'Lorem ipsum dolor sit amet, consectetur adipiscing elit',
            'bodyText': {'nodeType': 'document', 'data': {}, 'content': [{'nodeType': 'paragraph', 'data': {}, 'content': [{'value': 'Lorem ipsum:', 'nodeType': 'text', 'marks': [{'type': 'bold'}], 'data': {}}, {'value': ' dolor sit amet, consectetur adipiscing elit', 'nodeType': 'text', 'marks': [], 'data': {}}]}]}
        })
        featured_products_entry = create_contentful_entry('featuredProductsModule', {
            'internalName': 'Lorem ipsum dolor sit amet, consectetur adipiscing elit',
            'heading': 'Lorem ipsum dolor sit amet, consectetur adipiscing elit',
            'introduction': 'Lorem ipsum dolor sit amet, consectetur adipiscing elit',
            'productList': create_contentful_entry('textListModule', {
                'title': 'Lorem ipsum dolor sit amet, consectetur adipiscing elit',
                'theme': 'background-white',
                'textListItems': [create_contentful_entry('textListItem', {
                    'header': 'Lorem ipsum dolor sit amet, consectetur adipiscing elit',
                    'description': {'nodeType': 'document', 'data': {}, 'content': [{'nodeType': 'paragraph', 'data': {}, 'content': [{'value': 'Lorem ipsum:', 'nodeType': 'text', 'marks': [{'type': 'bold'}], 'data': {}}, {'value': ' dolor sit amet, consectetur adipiscing elit', 'nodeType': 'text', 'marks': [], 'data': {}}]}]}
                })]
            }),
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
        self.mock_contentful_degree_entry = create_contentful_entry('degreeDetailPage', {
            'internalName': 'Lorem ipsum dolor sit amet, consectetur adipiscing elit',
            'uuid': 'test-uuid',
            'seo': seo_entry,
            'hero': hero_entry,
            'modules': [
                about_the_program_entry,
                faq_entry,
                placement_about_section_entry,
                featured_products_entry
            ]
        })

        self.degree_transformed_data = {
            'test-uuid': {
                'page_title': 'Lorem ipsum dolor sit amet, consectetur adipiscing elit',
                'subheading': 'Lorem ipsum dolor sit amet, consectetur adipiscing elit',
                'about_program_heading': 'Lorem ipsum dolor sit amet, consectetur adipiscing elit',
                'about_program_content': 'Lorem ipsum dolor sit amet, consectetur adipiscing elit',
                'about_program_checkmarked_items': [
                    'Lorem ipsum: dolor sit amet, consectetur adipiscing elit'
                ],
                'faq_items': [
                    {
                        'question': 'Lorem ipsum dolor sit amet, consectetur adipiscing elit',
                        'answer': 'Lorem ipsum dolor sit amet, consectetur adipiscing elitLorem ipsum dolor sit amet,'
                        ' consectetur adipiscing elitLorem ipsum dolor sit amet, consectetur adipiscing elitLorem'
                        ' ipsum dolor sit amet, consectetur adipiscing elitLorem ipsum dolor sit amet, '
                        'consectetur adipiscing elitLorem ipsum dolor sit amet, consectetur adipiscing elit'
                    },
                ],
                "featured_products": {
                    "heading": "Lorem ipsum dolor sit amet, consectetur adipiscing elit",
                    "introduction": "Lorem ipsum dolor sit amet, consectetur adipiscing elit",
                    "product_list": [
                        {
                            "header": "Lorem ipsum dolor sit amet, consectetur adipiscing elit",
                            "description": "Lorem ipsum: dolor sit amet, consectetur adipiscing elit"
                        },
                    ],
                },
                "placement_about_section": {
                    "heading": "Lorem ipsum dolor sit amet, consectetur adipiscing elit",
                    "body_text": "Lorem ipsum: dolor sit amet, consectetur adipiscing elit",
                }
            }
        }
