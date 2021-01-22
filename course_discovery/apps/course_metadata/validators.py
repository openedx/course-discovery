from html.parser import HTMLParser

from django.core.exceptions import ValidationError
from django.utils.translation import ugettext as _


class HtmlValidator(HTMLParser):
    ALLOWED_TAGS = {
        'a', 'b', 'bdo', 'br', 'div', 'em', 'i', 'img', 'li', 'ol', 'p', 'span', 'strong',
        'table', 'td', 'th', 'tr', 'u', 'ul',
    }
    ALLOWED_ATTRS = {  # attrs allowed for any tag
        'align',  # rtl, formatting
        'dir',
        'lang',
        'style',  # allow for now, but we might want to reconsider this
        'typeof',  # a harmless semantic-web RDF thing, seen in the wild in our database
    }
    ALLOWED_TAG_ATTRS = {
        'a': {'href', 'rel', 'target', 'title'},
        'img': {'alt', 'height', 'src', 'width'},
        'ol': {'reversed', 'start', 'type'},
    }

    def error(self, message=None):
        """
        Be careful of putting bad html in your message, as this might end up in a log or somewhere it will be parsed.
        """
        if message:
            raise ValidationError(_('Invalid HTML received: {0}').format(message))
        raise ValidationError(_('Invalid HTML received'))

    def handle_starttag(self, tag, attrs):
        if tag not in self.ALLOWED_TAGS:
            self.error(_('{0} tag is not allowed').format(tag))

        # Also make sure there are no unexpected attributes
        attr_keys = {attr[0] for attr in attrs}  # attrs is a list of key, value tuples
        allowed_attrs = self.ALLOWED_ATTRS | self.ALLOWED_TAG_ATTRS.get(tag, frozenset())
        unknown_attrs = attr_keys - allowed_attrs
        if unknown_attrs:
            self.error(_('{0} attribute is not allowed on the {1} tag').format(unknown_attrs.pop(), tag))

    def handle_endtag(self, tag):
        if tag not in self.ALLOWED_TAGS:
            self.error(_('{0} tag is not allowed').format(tag))

    def handle_comment(self, data):
        self.error()

    def handle_decl(self, decl):
        self.error()

    def handle_pi(self, data):
        self.error()

    def unknown_decl(self, data):
        self.error()


def validate_html(content):
    if content:
        HtmlValidator().feed(content)
