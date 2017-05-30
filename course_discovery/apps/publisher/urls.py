"""
URLs for the course publisher views.
"""
from django.conf.urls import include, url

from course_discovery.apps.publisher import views

urlpatterns = [
    url(r'^$', views.Dashboard.as_view(), name='publisher_dashboard'),
    url(r'^api/', include('course_discovery.apps.publisher.api.urls', namespace='api')),
    url(r'^courses/$', views.CourseListView.as_view(), name='publisher_courses'),
    url(r'^courses/new/$', views.CreateCourseView.as_view(), name='publisher_courses_new'),
    url(r'^courses/(?P<pk>\d+)/$', views.CourseDetailView.as_view(), name='publisher_course_detail'),
    url(r'^courses/(?P<pk>\d+)/edit/$', views.CourseEditView.as_view(), name='publisher_courses_edit'),
    url(
        r'^courses/(?P<parent_course_id>\d+)/course_runs/new/$',
        views.CreateCourseRunView.as_view(),
        name='publisher_course_runs_new'
    ),
    url(r'^course_runs/(?P<pk>\d+)/$', views.CourseRunDetailView.as_view(), name='publisher_course_run_detail'),
    url(r'^course_runs/(?P<pk>\d+)/edit/$', views.CourseRunEditView.as_view(), name='publisher_course_runs_edit'),
    url(
        r'^course_runs/new/$',
        views.CreateRunFromDashboardView.as_view(),
        name='publisher_create_run_from_dashboard'
    ),

    url(
        r'^user/toggle/email_settings/$',
        views.ToggleEmailNotification.as_view(),
        name='publisher_toggle_email_settings'
    ),
    url(r'^courses/(?P<pk>\d+)/revisions/(?P<revision_id>\d+)/$', views.CourseRevisionView.as_view(),
        name='publisher_course_revision'),

    url(r'^admin/importcourses/$', views.AdminImportCourse.as_view(), name='publisher_admin_import_course'),
]
