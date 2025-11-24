from rest_framework import viewsets
from rest_framework.permissions import AllowAny
from course_discovery.apps.api.serializers import ProgramSerializer
from course_discovery.apps.course_metadata.models import Program


class PublicProgramViewSet(viewsets.ReadOnlyModelViewSet):
    """
    Public read-only endpoint for listing Programs.
    """
    queryset = Program.objects.all()  
    serializer_class = ProgramSerializer
    permission_classes = [AllowAny]
