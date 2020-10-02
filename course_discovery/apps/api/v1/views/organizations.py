from django_filters.rest_framework import DjangoFilterBackend
from guardian.shortcuts import get_objects_for_user
from rest_framework import viewsets
from rest_framework.permissions import IsAuthenticated

from course_discovery.apps.api import filters, serializers
from course_discovery.apps.api.cache import CompressedCacheResponseMixin
from course_discovery.apps.api.pagination import ProxiedPagination
from course_discovery.apps.publisher.models import OrganizationExtension


# pylint: disable=useless-super-delegation
class OrganizationViewSet(CompressedCacheResponseMixin, viewsets.ReadOnlyModelViewSet):
    """ Organization resource. """

    filter_backends = (DjangoFilterBackend,)
    filterset_class = filters.OrganizationFilter
    lookup_field = 'uuid'
    lookup_value_regex = '[0-9a-f-]+'
    permission_classes = (IsAuthenticated,)
    serializer_class = serializers.OrganizationSerializer

    # Explicitly support PageNumberPagination and LimitOffsetPagination. Future
    # versions of this API should only support the system default, PageNumberPagination.
    pagination_class = ProxiedPagination

    def get_queryset(self):
        user = self.request.user
        partner = self.request.site.partner

        if user.is_staff:
            return serializers.OrganizationSerializer.prefetch_queryset(partner=partner)
        else:
            organizations = get_objects_for_user(
                user,
                OrganizationExtension.VIEW_COURSE,
                OrganizationExtension,
                use_groups=True,
                with_superuser=False
            ).values_list('organization')
            orgs_queryset = serializers.OrganizationSerializer.prefetch_queryset(partner=partner).filter(
                pk__in=organizations
            )
            return orgs_queryset

    def list(self, request, *args, **kwargs):
        """ Retrieve a list of all organizations. """
        return super().list(request, *args, **kwargs)

    def retrieve(self, request, *args, **kwargs):
        """ Retrieve details for an organization. """
        return super().retrieve(request, *args, **kwargs)
