"""
Change the attributes you want to customize
"""


def get_model():
    from course_discovery.apps.publisher_comments.models import Comments
    return Comments


def get_form():
    from course_discovery.apps.publisher_comments.forms import CommentsForm
    return CommentsForm
