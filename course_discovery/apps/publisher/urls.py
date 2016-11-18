"""
URLs for the course publisher views.
"""
from django.conf.urls import url

from course_discovery.apps.publisher import views

urlpatterns = [
    url(r'^dashboard/$', views.Dashboard.as_view(), name='publisher_dashboard'),
    url(r'^courses/new$', views.CreateCourseView.as_view(), name='publisher_courses_new'),
    url(r'^courses/(?P<pk>\d+)/view/$', views.ReadOnlyView.as_view(), name='publisher_courses_readonly'),
    url(r'^courses/(?P<pk>\d+)/edit/$', views.UpdateCourseView.as_view(), name='publisher_courses_edit'),
    url(
        r'^courses/(?P<parent_course_id>\d+)/course_runs/new/$',
        views.CreateCourseRunView.as_view(),
        name='publisher_course_runs_new'
    ),
    url(r'^course_runs/(?P<pk>\d+)/$', views.CourseRunDetailView.as_view(), name='publisher_course_run_detail'),
    url(r'^course_runs/(?P<pk>\d+)/edit/$', views.UpdateCourseRunView.as_view(), name='publisher_course_runs_edit'),
    url(
        r'^course_runs/(?P<course_run_id>\d+)/change_state/$',
        views.ChangeStateView.as_view(),
        name='publisher_change_state'
    ),
    url(r'^seats/new/$', views.CreateSeatView.as_view(), name='publisher_seats_new'),
    url(r'^seats/(?P<pk>\d+)/edit/$', views.UpdateSeatView.as_view(), name='publisher_seats_edit'),
    url(
        r'^user/toggle/email_settings/$',
        views.ToggleEmailNotification.as_view(),
        name='publisher_toggle_email_settings'),
]
