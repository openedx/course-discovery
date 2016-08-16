"""
URLs for the course publisher views.
"""
from django.conf.urls import url

from course_discovery.apps.publisher_comments import views

urlpatterns = [
    url(r'^(?P<pk>\d+)/edit/$', views.UpdateCommentView.as_view(), name='comment_edit'),
]
