from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from course_discovery.apps.api.cache import CompressedCacheResponseMixin
from course_discovery.apps.api.serializers import BulkOperationTaskSerializer
from course_discovery.apps.course_metadata.models import BulkOperationTask


class BulkOperationTaskViewSet(CompressedCacheResponseMixin, viewsets.ModelViewSet):
    queryset = BulkOperationTask.objects.all()
    serializer_class = BulkOperationTaskSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        """
        Optionally restricts the returned tasks to a given user by filtering against a 'user' query parameter.
        """
        if self.request.user.is_superuser or self.request.user.is_staff:
            return super().get_queryset()
        return self.queryset.filter(uploaded_by=self.request.user)

    def perform_create(self, serializer):
        """
        Override perform_create to attach the current user to the instance being created.
        """
        serializer.save(uploaded_by=self.request.user)
