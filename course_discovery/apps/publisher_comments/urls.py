"""
URLs for the course publisher comments views.
"""
from django.conf.urls import url, include

from course_discovery.apps.publisher_comments import views

urlpatterns = [
    url(r'^api/', include('course_discovery.apps.publisher_comments.api.urls', namespace='api')),
    url(r'^(?P<pk>\d+)/edit/$', views.UpdateCommentView.as_view(), name='comment_edit'),
]
