'''JournalViewSet'''
from django_filters.rest_framework import DjangoFilterBackend

from course_discovery.apps.journal import constants as journal_constants
from course_discovery.apps.journal.api.filters import JournalFilter
from course_discovery.apps.journal.api.paginations import LargeResultsSetPagination
from course_discovery.apps.journal.api.serializers import JournalBundleSerializer, JournalSerializer
from course_discovery.apps.journal.models import Journal, JournalBundle
from rest_framework import viewsets
from rest_framework.permissions import IsAdminUser
from rest_framework_extensions.cache.mixins import CacheResponseMixin


class JournalViewSet(viewsets.ModelViewSet):
    """
    API endpoint that allows journals to be viewed or edited.
    """
    lookup_field = 'uuid'
    lookup_value_regex = journal_constants.UUID_PATTERN
    queryset = JournalSerializer.prefetch_queryset(Journal.objects.all())
    serializer_class = JournalSerializer
    filter_backends = (DjangoFilterBackend,)
    filter_class = JournalFilter
    permission_classes = (IsAdminUser,)
    pagination_class = LargeResultsSetPagination

    def list(self, request, *args, **kwargs):
        organization = request.GET.get('organization')
        if organization:
            self.queryset = self.get_queryset().filter(organization__key=organization)
        uuid = request.GET.get('uuid')  # uuid can be one or many separated by commas
        if uuid:
            self.queryset = self.get_queryset().filter(uuid__in=uuid.split(','))

        return super(JournalViewSet, self).list(request, *args, **kwargs)


class JournalBundleViewSet(CacheResponseMixin, viewsets.ReadOnlyModelViewSet):
    """ Journal Bundle"""
    lookup_field = 'uuid'
    lookup_value_regex = journal_constants.UUID_PATTERN
    permission_classes = (IsAdminUser,)
    filter_backends = (DjangoFilterBackend,)

    queryset = JournalBundleSerializer.prefetch_queryset(JournalBundle.objects.all())
    serializer_class = JournalBundleSerializer
    pagination_class = LargeResultsSetPagination
