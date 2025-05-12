""" ViewSet for BulkOperationTask model. """
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import mixins, viewsets
from rest_framework.filters import OrderingFilter

from course_discovery.apps.api.cache import CompressedCacheResponseMixin
from course_discovery.apps.api.filters import BulkOperationTaskFilter
from course_discovery.apps.api.permissions import IsStaffOrSuperuser
from course_discovery.apps.api.serializers import BulkOperationTaskSerializer
from course_discovery.apps.course_metadata.models import BulkOperationTask


class BulkOperationTaskViewSet(CompressedCacheResponseMixin, mixins.CreateModelMixin, mixins.RetrieveModelMixin,
                               mixins.ListModelMixin, viewsets.GenericViewSet):
    """
    ViewSet for BulkOperationTask model.
    """
    queryset = BulkOperationTask.objects.all()
    serializer_class = BulkOperationTaskSerializer
    permission_classes = [IsStaffOrSuperuser]
    filter_backends = (DjangoFilterBackend, OrderingFilter)
    filterset_class = BulkOperationTaskFilter
    ordering_fields = ('created', 'status')
    ordering = ('-created',)
    search_fields = ('task_type', 'uploaded_by__username')

    def perform_create(self, serializer):
        """
        Overriding perform_create to set the uploaded_by field to the current user.
        """
        serializer.save(uploaded_by=self.request.user)
