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
        Overriding get_queryset to filter tasks based on the user. If the user is a superuser or staff,
        they can see all tasks. Otherwise, they can only see their own tasks.
        """
        if self.request.user.is_superuser or self.request.user.is_staff:
            return super().get_queryset()
        return self.queryset.filter(uploaded_by=self.request.user)

    def perform_create(self, serializer):
        """
        Overriding perform_create to set the uploaded_by field to the current user.
        """
        serializer.save(uploaded_by=self.request.user)
