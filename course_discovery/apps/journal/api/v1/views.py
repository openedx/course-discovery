'''JournalViewSet'''
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import viewsets
from rest_framework_extensions.cache.mixins import CacheResponseMixin
from rest_framework.permissions import IsAuthenticated

from course_discovery.apps.journal.models import Journal, JournalBundle
from course_discovery.apps.journal.api.serializers import JournalSerializer, JournalBundleSerializer
from course_discovery.apps.journal import constants as journal_constants


class JournalViewSet(viewsets.ModelViewSet):
    """
    API endpoint that allows journals to be viewed or edited.
    """
    queryset = Journal.objects.all()
    serializer_class = JournalSerializer


class JournalBundleViewSet(CacheResponseMixin, viewsets.ReadOnlyModelViewSet):
    """ Journal Bundle"""
    lookup_field = 'uuid'
    lookup_value_regex = journal_constants.UUID_PATTERN
    permission_classes = (IsAuthenticated,)
    filter_backends = (DjangoFilterBackend,)

    queryset = JournalBundle.objects.all()
    serializer_class = JournalBundleSerializer
