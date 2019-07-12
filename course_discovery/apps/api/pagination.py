from rest_framework.pagination import LimitOffsetPagination
from rest_framework.pagination import PageNumberPagination as BasePageNumberPagination


class PageNumberPagination(BasePageNumberPagination):
    page_size_query_param = 'page_size'


class ProxiedCall:
    """
    Utility class used in conjunction with ProxiedPagination to route method
    calls between pagination classes.
    """

    def __init__(self, proxy, method_name):
        self.proxy = proxy
        self.method_name = method_name

    def __call__(self, *args, **kwargs):
        try:
            # Currently, the only methods on DRF pagination classes which accept
            # requests as positional arguments expect them as the second positional
            # argument. Hence, we expect the same to be true here. If DRF's pagination
            # classes are changed such that this is no longer true, code below will
            # break, loudly, so that the maintainer realizes there is a problem.
            request = args[1]
        except IndexError:
            request = None

        paginator = self._get_paginator(request=request if request else False)

        # Look up the method and call it.
        return getattr(paginator, self.method_name)(*args, **kwargs)

    def _get_paginator(self, request=False):
        for paginator, query_param in self.proxy.paginators:
            # DRF's ListModelMixin calls paginate_queryset() prior to get_paginated_response(),
            # storing the original request on the paginator's `request` attribute. If the paginator
            # has this attribute, it means we've routed a previous paginate_queryset() call
            # to it and should continue using it.
            is_request_stored = hasattr(paginator, 'request')

            # If a request is available, look for the presence of a query parameter
            # indicating that we should use this paginator.
            is_query_param_present = request and request.query_params.get(query_param)

            if is_request_stored or is_query_param_present:
                return paginator

        # If we don't have a stored request or query parameter to go off of,
        # default to the last paginator in the list on the proxy. To preserve
        # pre-existing behavior, this is currently LimitOffsetPagination.
        return paginator  # pylint: disable=undefined-loop-variable


class ProxiedPagination:
    """
    Pagination class which proxies to either DRF's PageNumberPagination or
    LimitOffsetPagination.

    The following are all valid:

        http://api.example.org/accounts/?page=4
        http://api.example.org/accounts/?page=4&page_size=100
        http://api.example.org/accounts/?limit=100
        http://api.example.org/accounts/?offset=400&limit=100

    If no query parameters are passed, proxies to LimitOffsetPagination by default.
    """

    def __init__(self):
        page_number_paginator = PageNumberPagination()
        limit_offset_paginator = LimitOffsetPagination()

        self.paginators = [
            (page_number_paginator, page_number_paginator.page_query_param),
            (limit_offset_paginator, limit_offset_paginator.limit_query_param),
        ]

    def __getattr__(self, name):
        # For each paginator, check if the requested attribute is defined.
        # If the attr is defined on both paginators, we take the one defined for
        # LimitOffsetPagination. As of this writing, `display_page_controls` is
        # the only attr shared by the two pagination classes.
        for paginator, __ in self.paginators:
            try:
                attr = getattr(paginator, name)
            except AttributeError:
                pass

        # The value defined for the attribute in the paginators may be None, which
        # prevents us from defaulting `attr` to None.
        try:
            attr
        except NameError:
            # The attribute wasn't found on either paginator.
            raise AttributeError
        else:
            # The attribute was found. If it's callable, return a ProxiedCall
            # which will route method calls to the correct paginator.
            if callable(attr):
                return ProxiedCall(self, name)
            else:
                return attr
