from rest_framework import serializers

from course_discovery.apps.publisher_comments.models import Comments


class CommentSerializer(serializers.ModelSerializer):

    class Meta:
        model = Comments
        fields = ('comment', 'modified', )
