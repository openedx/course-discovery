from django.test import TestCase

from course_discovery.apps.publisher_comments.api.serializers import CommentSerializer
from course_discovery.apps.publisher_comments.tests.factories import CommentFactory


class CommentSerializerTests(TestCase):
    def test_data(self):
        """ Verify that CommentsSerializer serialize the comment object. """

        comment = CommentFactory.create(comment='test comment')
        serializer = CommentSerializer(comment)
        expected = {'comment': 'test comment',
                    'modified': comment.modified.strftime("%Y-%m-%dT%H:%M:%S.%fZ")}

        self.assertDictEqual(serializer.data, expected)
