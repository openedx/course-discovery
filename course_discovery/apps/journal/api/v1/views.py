'''JournalViewSet'''
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import viewsets
from rest_framework.permissions import IsAdminUser
from rest_framework_extensions.cache.mixins import CacheResponseMixin

from course_discovery.apps.journal import constants as journal_constants
from course_discovery.apps.journal.api.filters import JournalFilter
from course_discovery.apps.journal.api.serializers import JournalBundleSerializer, JournalSerializer
from course_discovery.apps.journal.models import Journal, JournalBundle


class JournalViewSet(viewsets.ModelViewSet):
    """
    API endpoint that allows journals to be viewed or edited.
    """
    lookup_field = 'uuid'
    lookup_value_regex = journal_constants.UUID_PATTERN
    queryset = Journal.objects.all().order_by('-created')
    serializer_class = JournalSerializer
    filter_backends = (DjangoFilterBackend,)
    filter_class = JournalFilter
    permission_classes = (IsAdminUser,)


class JournalBundleViewSet(CacheResponseMixin, viewsets.ReadOnlyModelViewSet):
    """ Journal Bundle"""
    lookup_field = 'uuid'
    lookup_value_regex = journal_constants.UUID_PATTERN
    permission_classes = (IsAdminUser,)
    filter_backends = (DjangoFilterBackend,)

    queryset = JournalBundle.objects.all()
    serializer_class = JournalBundleSerializer
