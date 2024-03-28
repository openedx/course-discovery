"""
Mixins for the API application.
"""
# pylint: disable=not-callable
import math

from django.contrib.auth.models import AnonymousUser
from elasticsearch.exceptions import RequestError
from rest_framework import status
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.throttling import AnonRateThrottle

from course_discovery.apps.edx_elasticsearch_dsl_extensions.backends import (
    FacetedFieldSearchFilterBackend, FacetedQueryFilterBackend
)
from course_discovery.apps.edx_elasticsearch_dsl_extensions.exceptions import InvalidQuery


class FacetMixin:
    """
    Mixin class for supporting faceting on an API View.
    """

    facet_serializer_class = None
    facet_objects_serializer_class = None
    facet_query_params_text = 'selected_facets'

    def dispatch(self, request, *args, **kwargs):
        self.filter_backends = [
            backend
            for backend in self.filter_backends
            if backend not in (FacetedQueryFilterBackend, FacetedFieldSearchFilterBackend)
        ]
        response = super().dispatch(request, *args, **kwargs)

        return response

    @action(detail=False, methods=['get'], url_path='facets')
    def facets(self, request):
        """
        Sets up a list route for ``faceted`` results.

        This will add ie ^search/facets/$ to your existing ^search pattern.
        """
        if hasattr(self, 'faceted_query_filter_fields'):
            self.filter_backends.append(FacetedQueryFilterBackend)
        if hasattr(self, 'faceted_search_fields'):
            self.filter_backends.append(FacetedFieldSearchFilterBackend)
        queryset = self.filter_facet_queryset(self.get_queryset())

        search_res = queryset.execute()
        dicted_facets = search_res.facets.to_dict()
        serializer = self.get_facet_serializer(dicted_facets, objects=queryset, many=False)
        return Response(serializer.data)

    def get_facet_serializer(self, *args, **kwargs):
        """
        Get serialized facet object.

        Return the facet serializer instance that should be used for
        serializing faceted output.
        """
        assert 'objects' in kwargs, '`objects` is a required naming argument.'
        facet_serializer_class = self.get_facet_serializer_class()
        kwargs['context'] = self.get_serializer_context()
        kwargs['context'].update(
            {'objects': kwargs.pop('objects'), 'facet_query_params_text': self.facet_query_params_text}
        )
        return facet_serializer_class(*args, **kwargs)

    def get_facet_serializer_class(self):
        """
        Return the class to use for serializing facets.
        Defaults to using ``self.facet_serializer_class``.
        """
        if self.facet_serializer_class is None:
            raise AttributeError(
                '%(cls)s should either include a `facet_serializer_class` attribute, '
                'or override %(cls)s.get_facet_serializer_class() method.' % {'cls': self.__class__.__name__}
            )
        return self.facet_serializer_class

    def get_facet_objects_serializer(self, *args, **kwargs):
        """
        Return the serializer instance, which should be used for
        serializing faceted objects.
        """
        facet_objects_serializer_class = self.get_facet_objects_serializer_class()
        kwargs['context'] = self.get_serializer_context()
        return facet_objects_serializer_class(*args, **kwargs)

    def get_facet_objects_serializer_class(self):
        """
        Return the class to use for serializing faceted objects.
        Defaults to using the views ``self.serializer_class`` if not
        ``self.facet_objects_serializer_class`` is set.
        """
        return self.facet_objects_serializer_class or super().get_serializer_class()


class ValidElasticSearchQueryRequiredMixin:
    """
    Mixin to catch invalid Elasticsearch query string exception.
    """

    def dispatch(self, request, *args, **kwargs):
        try:
            return super().dispatch(request, *args, **kwargs)
        except RequestError as exc:
            self.args = args
            self.kwargs = kwargs
            request = self.initialize_request(request, *args, **kwargs)
            self.request = request
            self.headers = self.default_response_headers
            exception = InvalidQuery(f'Failed to make Elasticsearch request. Got exception: {exc}')
            response = self.handle_exception(exception)
            self.response = self.finalize_response(request, response, *args, **kwargs)

            return self.response


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
            "or override the `get_detail_serializer_class()` method." % self.__class__.__name__
        )
        return self.detail_serializer_class


class AnonymousUserThrottleAuthenticatedEndpointMixin:
    """
    Mixin to perform anonymous user throttling on API endpoints that require authentication.

    Utilize anonymous_user_throttle_class attribute on View to determine the throttle instance, falling back to
    AnonRateThrottle if not provided. This is a patchy workaround to run throttling against unauthenticated users
    hitting an endpoint that requires Authentication. The evaluation order of DRF is authentication, permissions, and
    throttling. If user is unauthenticated, the throttle checks are not performed because authentication evaluation
    stops code flow. This leaves API vulnerable to unauth requests brute force attack.

    See https://github.com/encode/django-rest-framework/issues/5234 for more context.
    """
    def dispatch(self, request, *args, **kwargs):
        initialized_request = self.initialize_request(request, *args, **kwargs)
        user = initialized_request.user
        if isinstance(user, AnonymousUser) and (
                self.authentication_classes or (self.permission_classes and IsAuthenticated in self.permission_classes)
        ):
            throttle_instance = getattr(self, 'anonymous_user_throttle_class', AnonRateThrottle)()
            if not throttle_instance.allow_request(request, self):
                # The following set of lines are similar to how dispatch works in DRF.
                # This bare minimum is there to ensure the response meets DRF requirements.
                # Similar thing is already being done in ValidElasticSearchQueryRequiredMixin.
                wait = math.ceil(throttle_instance.wait())
                self.args = args
                self.kwargs = kwargs
                self.request = initialized_request
                self.headers = {**self.default_response_headers, 'Retry-After': wait}
                self.format_kwarg = self.get_format_suffix(**kwargs)
                response = Response(
                    {"detail": f"Request was throttled. Expected available in {wait} seconds."},
                    status=status.HTTP_429_TOO_MANY_REQUESTS
                )
                return self.finalize_response(self.request, response, *args, **kwargs)
        return super().dispatch(request, *args, **kwargs)
