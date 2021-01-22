"""
Mixins for the API application.
"""
# pylint: disable=not-callable

from rest_framework.decorators import action
from rest_framework.response import Response


class DetailMixin:
    """Mixin for adding in a detail endpoint using a special detail serializer."""

    detail_serializer_class = None

    @action(detail=False, methods=['get'])
    def details(self, request):
        """
        List detailed results.
        ---
        parameters:
            - name: q
              description: Search text
              paramType: query
              type: string
              required: false
        """
        queryset = self.filter_queryset(self.get_queryset())

        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = self.get_detail_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)

        serializer = self.get_detail_serializer(queryset, many=True)
        return Response(serializer.data)

    def get_detail_serializer(self, *args, **kwargs):
        """
        Return the serializer instance that should be used for validating and
        deserializing input, and for serializing output.
        """
        serializer_class = self.get_detail_serializer_class()
        kwargs['context'] = self.get_serializer_context()
        return serializer_class(*args, **kwargs)

    def get_detail_serializer_class(self):
        """
        Return the class to use for the serializer.
        Defaults to using `self.detail_serializer_class`.
        """
        assert self.detail_serializer_class is not None, (
            "'%s' should either include a `detail_serializer_class` attribute, "
            "or override the `get_detail_serializer_class()` method."
            % self.__class__.__name__
        )
        return self.detail_serializer_class
