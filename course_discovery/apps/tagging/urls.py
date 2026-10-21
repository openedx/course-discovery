from django.urls import path

from course_discovery.apps.tagging.views import (
    CourseListView, CourseTaggingDetailView, SubVerticalDetailView, SubVerticalListView, VerticalDetailView,
    VerticalListView
)

app_name = 'tagging'

urlpatterns = [
    path('courses/<uuid:uuid>/', CourseTaggingDetailView.as_view(), name='course_tagging_detail'),
    path('verticals/<slug:slug>/', VerticalDetailView.as_view(), name='vertical_detail'),
    path('sub_verticals/<slug:slug>/', SubVerticalDetailView.as_view(), name='sub_vertical_detail'),
    path('courses/', CourseListView.as_view(), name='course_list'),
    path('verticals/', VerticalListView.as_view(), name='vertical_list'),
    path('sub_verticals/', SubVerticalListView.as_view(), name='sub_vertical_list'),
]
