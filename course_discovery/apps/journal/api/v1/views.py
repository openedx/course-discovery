'''JournalViewSet'''
from rest_framework import viewsets

from course_discovery.apps.journal.models import Journal
from course_discovery.apps.journal.api.serializers import JournalSerializer


class JournalViewSet(viewsets.ModelViewSet):
    """
    API endpoint that allows journals to be viewed or edited.
    """
    queryset = Journal.objects.all()
    serializer_class = JournalSerializer
