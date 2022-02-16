"""
Utils for loaders to format or transform field values.
"""
from lxml.html import clean

from course_discovery.apps.course_metadata.validators import HtmlValidator


class HtmlCleaner():
    """
    Custom html cleaner inline with validator rules.
    """

    def __init__(self):
        ALLOWED_TAGS = HtmlValidator.ALLOWED_TAGS
        ALLOWED_ATTRS = HtmlValidator.ALLOWED_ATTRS
        ALLOWED_TAG_ATTRS = HtmlValidator.ALLOWED_TAG_ATTRS

        for attribs in ALLOWED_TAG_ATTRS.values():
            ALLOWED_ATTRS = ALLOWED_ATTRS.union(attribs)

        self.cleaner = clean.Cleaner(
            safe_attrs_only=True,
            safe_attrs=frozenset(ALLOWED_ATTRS),
            allow_tags=ALLOWED_TAGS
        )


cleaner = HtmlCleaner().cleaner


def p_tag(text):
    """
    Convert text string into html p tag
    """
    return f"<p>{text}</p>"


def format_faqs(data):
    """
    Format list of faqs as one html text string.
    """
    formatted_html = ""
    for faq in data:
        headline = faq['headline']
        blurb = faq['blurb']
        formatted_html += p_tag(f"<b>{headline}</b>") + blurb

    return cleaner.clean_html(formatted_html) if formatted_html else formatted_html


def format_curriculum(data):
    """
    Format list of modules in curriculum as one html text string.
    """
    formatted_html = ""
    if 'blurb' in data:
        blurb = data['blurb']
        formatted_html = p_tag(blurb) if blurb else ""

    if 'modules' in data:
        for modules in data['modules']:
            heading = modules['heading']
            description = modules['description']
            formatted_html += p_tag(f"<b>{heading}: </b>{description}")

    return cleaner.clean_html(formatted_html) if formatted_html else formatted_html


def format_testimonials(data):
    """
    Format list of testimonials as one html text string.
    """
    formatted_html = ""
    for testimonial in data:
        name = testimonial['name']
        title = testimonial['title']
        text = testimonial['text']
        formatted_html += p_tag(f"<i>\"{text}\"</i>") + p_tag(f"-{name} ({title})")

    return cleaner.clean_html(formatted_html) if formatted_html else formatted_html
