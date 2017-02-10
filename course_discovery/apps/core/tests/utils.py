import json
import math
from urllib.parse import parse_qs, urlparse

from factory.fuzzy import BaseFuzzyAttribute, FuzzyChoice, FuzzyText

from course_discovery.apps.core.tests.helpers import make_image_stream


class FuzzyDomain(BaseFuzzyAttribute):
    def fuzz(self):
        subdomain = FuzzyText()
        domain = FuzzyText()
        tld = FuzzyChoice(('com', 'net', 'org', 'biz', 'pizza', 'coffee', 'diamonds', 'fail', 'win', 'wtf',))

        return "{subdomain}.{domain}.{tld}".format(
            subdomain=subdomain.fuzz(),
            domain=domain.fuzz(),
            tld=tld.fuzz()
        )


class FuzzyUrlRoot(BaseFuzzyAttribute):
    def fuzz(self):
        protocol = FuzzyChoice(('http', 'https',))
        domain = FuzzyDomain()

        return "{protocol}://{domain}".format(
            protocol=protocol.fuzz(),
            domain=domain.fuzz()
        )


class FuzzyURL(BaseFuzzyAttribute):
    def fuzz(self):
        root = FuzzyUrlRoot()
        resource = FuzzyText()

        return "{root}/{resource}".format(
            root=root.fuzz(),
            resource=resource.fuzz()
        )


def mock_api_callback(url, data, results_key=True, pagination=False):
    def request_callback(request):
        # pylint: disable=redefined-builtin

        count = len(data)
        next_url = None
        previous_url = None

        # Use the querystring to determine which page should be returned. Default to page 1.
        # Note that the values of the dict returned by `parse_qs` are lists, hence the `[1]` default value.
        qs = parse_qs(urlparse(request.path_url).query)
        page = int(qs.get('page', [1])[0])
        page_size = int(qs.get('page_size', [1])[0])

        if (page * page_size) < count:
            next_page = page + 1
            next_url = '{}?page={}'.format(url, next_page)

        if page > 1:
            previous_page = page - 1
            previous_url = '{}?page={}'.format(url, previous_page)

        body = {
            'count': count,
            'next': next_url,
            'num_pages': math.ceil(count / page_size),
            'previous': previous_url,
        }

        if pagination:
            body = {
                'pagination': body
            }
        if results_key:
            body['results'] = data
        else:
            body.update(data)

        return 200, {}, json.dumps(body)

    return request_callback


def mock_jpeg_callback():
    def request_callback(request):  # pylint: disable=unused-argument
        image_stream = make_image_stream(2120, 1192)

        return 200, {}, image_stream.getvalue()

    return request_callback
