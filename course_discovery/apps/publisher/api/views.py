import re

from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.generics import ListAPIView, get_object_or_404
from rest_framework.pagination import CursorPagination
from rest_framework.permissions import IsAuthenticated

from course_discovery.apps.core.models import User
from course_discovery.apps.publisher.api.filters import OrganizationUserRoleFilterSet
from course_discovery.apps.publisher.api.paginations import LargeResultsSetPagination
from course_discovery.apps.publisher.api.permissions import PublisherUserPermission
from course_discovery.apps.publisher.api.serializers import GroupUserSerializer, OrganizationUserRoleSerializer
from course_discovery.apps.publisher.models import OrganizationExtension, OrganizationUserRole

id_regex = re.compile(r'\d+')


class OrganizationUserRoleView(ListAPIView):
    """ List view for OrganizationUserRole """
    filter_backends = (DjangoFilterBackend,)
    filterset_class = OrganizationUserRoleFilterSet
    pagination_class = CursorPagination
    permission_classes = (IsAuthenticated, PublisherUserPermission)
    serializer_class = OrganizationUserRoleSerializer

    def get_queryset(self):
        pk = self.kwargs.get('pk')
        lookup = {'organization': pk} if id_regex.fullmatch(pk) else {'organization__uuid': pk}
        return OrganizationUserRole.objects.filter(**lookup)


class OrganizationGroupUserView(ListAPIView):
    """ List view for Users filtered by group """
    serializer_class = GroupUserSerializer
    permission_classes = (IsAuthenticated, PublisherUserPermission)
    pagination_class = LargeResultsSetPagination

    def get_queryset(self):
        pk = self.kwargs.get('pk')
        lookup = {'organization': pk} if id_regex.fullmatch(pk) else {'organization__uuid': pk}
        org_extension = get_object_or_404(OrganizationExtension, **lookup)
        return User.objects.filter(groups__organization_extension=org_extension).order_by('full_name', 'username')


class OrganizationUserView(ListAPIView):
    """ List view for all users in requester's organizations """
    serializer_class = GroupUserSerializer
    permission_classes = (IsAuthenticated, PublisherUserPermission)

    def get_queryset(self):
        user = self.request.user
        if user.is_staff:
            partner = self.request.site.partner
            organization_extensions = OrganizationExtension.objects.filter(organization__partner=partner)
            return User.objects.filter(
                groups__organization_extension__in=organization_extensions).distinct().order_by('full_name')

        return User.objects.filter(
            groups__organization_extension__group__in=user.groups.all()).distinct().order_by('full_name')
