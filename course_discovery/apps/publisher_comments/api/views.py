from rest_framework.generics import UpdateAPIView
from rest_framework.permissions import IsAuthenticated

from course_discovery.apps.publisher_comments.api.permissions import IsOwner
from course_discovery.apps.publisher_comments.api.serializers import CommentSerializer
from course_discovery.apps.publisher_comments.models import Comments


class UpdateCommentView(UpdateAPIView):
    serializer_class = CommentSerializer
    queryset = Comments.objects.all()
    permission_classes = (IsAuthenticated, IsOwner)
