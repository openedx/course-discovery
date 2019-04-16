from course_discovery.apps.publisher_comments.models import Comments
from rest_framework import serializers


class CommentSerializer(serializers.ModelSerializer):

    class Meta:
        model = Comments
        fields = ('comment', 'modified', )
