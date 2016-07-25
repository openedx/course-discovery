"""
URLs for the course publisher views.
"""
from django.conf.urls import url

from course_discovery.apps.publisher import views

urlpatterns = [
    url(r'^course/$', views.CreateCourseView.as_view(), name='publisher_course'),
    url(r'^course/edit/(?P<pk>\d+)/$', views.UpdateCourseView.as_view(), name='edit_course'),
    url(r'^course_run/$', views.CreateCourseRunView.as_view(), name='publisher_course_run'),
    url(r'^course_run/edit/(?P<pk>\d+)/$', views.UpdateCourseRunView.as_view(), name='edit_course_run'),
    url(r'^course_runs/$', views.CourseRunListView.as_view(), name='publisher_course_runs'),
    url(r'^course_runs/(?P<pk>\d+)/$', views.CourseRunDetailView.as_view(), name='publisher_course_run_detail'),

]
