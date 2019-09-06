""" Publisher comments API URLs. """
from django.conf.urls import url

from course_discovery.apps.publisher_comments.api import views

app_name = 'api'

urlpatterns = [
    url(r'^comments/(?P<pk>\d+)/$', views.UpdateCommentView.as_view(), name='comments'),
]
