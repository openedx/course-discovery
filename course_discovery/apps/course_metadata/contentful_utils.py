"""
Contains all utility functions for Contentful.
"""
import logging

from contentful import Client
from django.conf import settings
from django.core.cache import cache

logger = logging.getLogger(__name__)


def contentful_cache_key(content_type):
    """
    Cache key for bootcamp data from Contentful.
    """
    return 'contentful_bootcamp_data_key' if content_type == settings.BOOTCAMP_CONTENTFUL_CONTENT_TYPE else None


def get_data_from_contentful(content_type):
    """
    Utility function to get data from Contentful. Returns contentful entries of the content_type.
    Since fetching all objects results in a large amount of data, it gives us `Response size too big` error.
    We're fetching 10 objects per Contentful Client call and returning an appended response.

    Args:
        content_type (str): Contentful table-like instance comprised of fields.
    """
    cache_key = contentful_cache_key(content_type)
    cached_entries = cache.get(cache_key)
    if cached_entries:
        logger.info(f"Using cached Contentful entries data and skipping API call for {content_type}")
        return cached_entries

    client = Client(
        settings.CONTENTFUL_SPACE_ID,
        settings.CONTENTFUL_CONTENT_DELIVERY_API_KEY,
        environment=settings.CONTENTFUL_ENVIRONMENT,
        timeout_s=30  # increases read timeout
    )
    limit = 10
    skip = 10
    include = 5  # the depth of linked entries to be fetched from contentful
    total_entries = []
    contentful_entries = client.entries({
        'content_type': content_type,
        'limit': limit,
        'include': include
    })
    total_entries.extend(contentful_entries.items)
    total_count = contentful_entries.total
    logger.info(f'Fetching a total of {total_count} Contentful Entries for Content Type [{content_type}]')
    logger.info(f'Successfully fetched Contentful Entries from 1 to {skip}')

    while skip < total_count:
        contentful_entries = client.entries({
            'content_type': content_type,
            'limit': limit,
            'skip': skip,
            'include': include
        })
        if contentful_entries:
            total_entries.extend(contentful_entries.items)
            logger.info(f'Successfully fetched Contentful Entries from {skip + 1} to '
                        f'{skip + limit if skip + limit < total_count else total_count}')
            skip += limit

    # cache contentful API response for one day
    cache.set(cache_key, total_entries, timeout=60 * 60 * 24)

    return total_entries


def extract_plain_text_from_rich_text(rich_text_dict):
    """
    Recursive function to extract a list of values of all the keys containing plain text.

    Example:
    The incoming rich_text_dict is like this:
    {
        'nodeType': 'document',
        'data': {},
        'content': [
            {
                'nodeType': 'unordered-list',
                'data': {},
                'content': [
                    {
                        'nodeType': 'list-item',
                        'data': {},
                        'content': [
                            {
                                'nodeType': 'paragraph',
                                'data': {},
                                'content': [
                                    {
                                        'value': 'Lorem ipsum:',
                                        'nodeType': 'text',
                                        'marks': [{'type': 'bold'}],
                                        'data': {}
                                    },
                                    {
                                        'value': ' dolor sit amet, consectetur adipiscing elit.',
                                        'nodeType': 'text',
                                        'marks': [],
                                        'data': {}
                                    }
                                ]
                            }
                        ]
                    },
                    {
                        'nodeType': 'list-item',
                        'data': {},
                        'content': [
                            {
                                'nodeType': 'paragraph',
                                'data': {},
                                'content': [
                                    {
                                        'value': 'Excepteur sint:',
                                        'nodeType': 'text',
                                        'marks': [{'type': 'bold'}],
                                        'data': {}
                                    },
                                    {
                                        'value': ' occaecat cupidatat non proident.',
                                        'nodeType': 'text',
                                        'marks': [],
                                        'data': {}
                                    }
                                ]
                            }
                        ]
                    }
                ]
            }
        ]
    }

    This utility will returns this plain text:
    "Lorem ipsum:  dolor sit amet, consectetur adipiscing elit. Excepteur sint: occaecat cupidatat non proident."
    """
    text_list = []
    for key, value in rich_text_dict.items():
        if key == 'value':
            text_list.append(value)
        elif isinstance(value, dict):  # recursive call if the value is a nested dict
            text_list += extract_plain_text_from_rich_text(value)
        elif isinstance(value, list):  # recursive call if the value is a nested list
            for item in value:
                text_list += extract_plain_text_from_rich_text(item)
    return text_list


def rich_text_to_plain_text(rich_text):
    """
    Converts rich text from Contentful to plain text.
    Plain text resides in the dict with 'value' as dict key name.
    """
    return ''.join(extract_plain_text_from_rich_text(rich_text))


def get_modules_list(entry):
    """
    Given a contentful entry, returns a list of module names of all the modules.
    """
    module_list = []
    for module in entry.modules:
        module_list.append(module.sys.get('content_type').id)

    return module_list


def get_about_the_program_module(about_the_program_module):
    """
    Given a Contentful about the program module, extracts related data and returns them in the form of a dict.
    """
    about_program_heading = about_the_program_module.heading
    about_program_content = rich_text_to_plain_text(about_the_program_module.content)

    checkmarked_items_text_list_module = about_the_program_module.checkmarked_items.text_list_items
    about_program_checkmarked_items = []

    for checkmarked_item in checkmarked_items_text_list_module:
        about_program_checkmarked_items.append(rich_text_to_plain_text(checkmarked_item.description))

    return {
        'about_program_heading': about_program_heading,
        'about_program_content': about_program_content,
        'about_program_checkmarked_items': about_program_checkmarked_items
    }


def get_blurb_module(blurb_module):
    """
    Given a Contentful blurb module, extracts related data and returns them in the form of a dict.
    """
    blurb_1_heading = blurb_module.blurb_heading
    blurb_1_body = rich_text_to_plain_text(blurb_module.blurb_body)

    return {
        'blurb_1_heading': blurb_1_heading,
        'blurb_1_body': blurb_1_body
    }


def get_bootcamp_curriculum_module(bootcamp_curriculum_module):
    """
    Given a Contentful bootcamp curriculum module, extracts related data and returns both dict and faqs.
    """
    bootcamp_curriculum_heading = rich_text_to_plain_text(bootcamp_curriculum_module.subheading)
    bootcamp_curriculum_faqs = get_faq_module(bootcamp_curriculum_module.items)

    return {'bootcamp_curriculum_heading': bootcamp_curriculum_heading}, bootcamp_curriculum_faqs


def get_faq_module(faq_module):
    """
    Given a Contentful faq module, extracts related data and returns them in the form of a dict.
    """
    faq_items = []
    for faq_item in faq_module:
        faq_question = faq_item.question
        faq_answer = rich_text_to_plain_text(faq_item.answer_rich_text)
        faq_items.append({
            'question': faq_question,
            'answer': faq_answer,
        })
    return faq_items


def get_partnership_module(partnership_module):
    """
    Given a Contentful partnership module, extracts related data and returns them in the form of a dict.
    """
    partnership_heading_text = rich_text_to_plain_text(partnership_module.heading_text)
    partnership_body_text = rich_text_to_plain_text(partnership_module.body_text)

    return {
        'partnership_heading_text': partnership_heading_text,
        'partnership_body_text': partnership_body_text
    }


def fetch_and_transform_bootcamp_contentful_data():
    """
    Transforms incoming bootcamp data from contentful to algolia-usable form.

    Each Contentful entry has seo, hero and modules list.
    Each rich text content field has been transformed into plain text using `rich_text_to_plain_text`.
    """
    contentful_bootcamp_page_entries = get_data_from_contentful(settings.BOOTCAMP_CONTENTFUL_CONTENT_TYPE)
    transformed_bootcamp_data = {}
    for bootcamp_entry in contentful_bootcamp_page_entries:
        product_uuid = bootcamp_entry.uuid
        page_title = bootcamp_entry.seo.page_title
        subheading = bootcamp_entry.hero.subheading
        hero_text_list = rich_text_to_plain_text(bootcamp_entry.hero.text_list)

        transformed_bootcamp_data[product_uuid] = {
            'page_title': page_title,
            'subheading': subheading,
            'hero_text_list': hero_text_list,
        }

        module_list = get_modules_list(bootcamp_entry)

        if 'aboutTheProgramModule' in module_list:
            about_the_program = get_about_the_program_module(
                bootcamp_entry.modules[module_list.index('aboutTheProgramModule')]
            )
            transformed_bootcamp_data[product_uuid].update(about_the_program)

        if 'blurbModule' in module_list:
            blurb_indexes = [i for i, x in enumerate(module_list) if x == 'blurbModule']
            blurb_1 = get_blurb_module(bootcamp_entry.modules[blurb_indexes[0]])
            transformed_bootcamp_data[product_uuid].update(blurb_1)
            if len(blurb_indexes) == 2:
                blurb_2 = get_blurb_module(bootcamp_entry.modules[blurb_indexes[1]])
                transformed_bootcamp_data[product_uuid].update(blurb_2)

        faq_items = []
        if 'bootCampCurriculumModule' in module_list:
            bootcamp_curriculum_module, bootcamp_curriculum_faqs = get_bootcamp_curriculum_module(
                bootcamp_entry.modules[module_list.index('bootCampCurriculumModule')]
            )
            faq_items += bootcamp_curriculum_faqs
            transformed_bootcamp_data[product_uuid].update(bootcamp_curriculum_module)

        if 'partnershipModule' in module_list:
            partnership_module = get_partnership_module(bootcamp_entry.modules[module_list.index('partnershipModule')])
            transformed_bootcamp_data[product_uuid].update(partnership_module)

        if 'faqModule' in module_list:
            faq_module = get_faq_module(bootcamp_entry.modules[module_list.index('faqModule')].faqs)
            faq_items += faq_module
            transformed_bootcamp_data[product_uuid].update({'faq_items': faq_items})

    return transformed_bootcamp_data


def get_aggregated_data_from_contentful_data(data, product_uuid):
    if (data is None) or (product_uuid not in data):
        return None
    faqs = [f"{faq['question']} {faq['answer']}" for faq in data[product_uuid]['faq_items']]
    aggregated_text = ' '.join(faqs)
    if 'hero_text_list' in data[product_uuid]:
        aggregated_text = aggregated_text + ' ' + data[product_uuid]['hero_text_list']
    return aggregated_text
