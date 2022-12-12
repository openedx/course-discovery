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

mock_contentful_bootcamp_entry = create_contentful_entry('bootCampPage', {
    'internalName': 'Lorem ipsum dolor sit amet, consectetur adipiscing elit',
    'uuid': 'test-uuid',
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

bootcamp_transformed_data = {
    'test-uuid': {
        'page_title': 'Lorem ipsum dolor sit amet, consectetur adipiscing elit',
        'subheading': 'Lorem ipsum dolor sit amet, consectetur adipiscing elit',
        'hero_text_list': 'Lorem ipsum: dolor sit amet, consectetur adipiscing elitLorem ipsum: dolor sit amet,'
                          ' consectetur adipiscing elitLorem ipsum: dolor sit amet, consectetur adipiscing elitLorem'
                          ' ipsum: dolor sit amet, consectetur adipiscing elit',
        'about_program_heading': 'Lorem ipsum dolor sit amet, consectetur adipiscing elit',
        'about_program_content': 'Lorem ipsum dolor sit amet, consectetur adipiscing elit',
        'about_program_checkmarked_items': ['Lorem ipsum: dolor sit amet, consectetur adipiscing elit'],
        'blurb_1_heading': 'Lorem ipsum dolor sit amet, consectetur adipiscing elit',
        'blurb_1_body': 'Lorem ipsum dolor sit amet, consectetur adipiscing elitLorem ipsum dolor sit amet, consectetur'
                        ' adipiscing elitLorem ipsum dolor sit amet, consectetur adipiscing elit',
        'bootcamp_curriculum_heading': 'Lorem ipsum dolor sit amet, consectetur adipiscing elitLorem ipsum dolor sit '
                                       'amet, consectetur adipiscing elitLorem ipsum dolor sit amet, consectetur '
                                       'adipiscing elitLorem ipsum dolor sit amet, consectetur adipiscing elitLorem '
                                       'ipsum dolor sit amet, consectetur adipiscing elitLorem ipsum dolor sit amet,'
                                       ' consectetur adipiscing elitLorem ipsum dolor sit amet, consectetur '
                                       'adipiscing elit',
        'partnership_heading_text': 'Lorem ipsum dolor sit amet, consectetur adipiscing elit',
        'partnership_body_text': 'Lorem ipsum dolor sit amet, consectetur adipiscing elitLorem, ipsum, or dolorLorem '
                                 'ipsum dolor sit amet, consectetur adipiscing elit',
        'faq_items': [
            {
                'question': 'Lorem ipsum dolor sit amet, consectetur adipiscing elit',
                'answer': 'Lorem ipsum dolor sit amet, consectetur adipiscing elitLorem ipsum dolor sit amet,'
                          ' consectetur adipiscing elitLorem ipsum dolor sit amet, consectetur adipiscing elitLorem'
                          ' ipsum dolor sit amet, consectetur adipiscing elitLorem ipsum dolor sit amet, '
                          'consectetur adipiscing elitLorem ipsum dolor sit amet, consectetur adipiscing elit'
            },
            {
                'question': 'Lorem ipsum dolor sit amet, consectetur adipiscing elit',
                'answer': 'Lorem ipsum dolor sit amet, consectetur adipiscing elitLorem ipsum dolor sit amet, '
                          'consectetur adipiscing elitLorem ipsum dolor sit amet, consectetur adipiscing elitLorem'
                          ' ipsum dolor sit amet, consectetur adipiscing elitLorem ipsum dolor sit amet, consectetur'
                          ' adipiscing elitLorem ipsum dolor sit amet, consectetur adipiscing elit'
            }
        ]
    }
}


class MockContentBootcampResponse:
    """
    Mock response received from Contentful for bootcamp
    """
    items = [mock_contentful_bootcamp_entry]
    total = 15
