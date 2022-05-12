from rest_framework import permissions
from rest_framework.generics import ListAPIView
from rest_framework.response import Response

from course_discovery.apps.course_metadata.models import Course
from course_discovery.apps.taxonomy_support.api.v1.serializers import CourseRecommendationsSerializer


class CourseRecommendationsAPIView(ListAPIView):
    """
    Course recommendations API.
    Example:
        GET discovery.edx.org/taxonomy/api/v1/course_recommendations/edX+DemoX/
    """
    permission_classes = (permissions.IsAuthenticated,)
    queryset = Course.objects.all()
    serializer_class = CourseRecommendationsSerializer
    lookup_field = 'key'
    lookup_url_kwarg = 'course_key'

    def list(self, request, *args, **kwargs):
        course = self.get_object()
        queryset = course.course_recommendations.all().order_by(
            '-skills_intersection_ratio',
            '-skills_intersection_length',
            '-subjects_intersection_ratio',
            '-subjects_intersection_length',
            '-recommended_course__enrollment_count'
        )
        serializer_class = self.get_serializer_class()
        queryset = serializer_class.apply_prefetch(queryset)

        all_recommendations_queryset = queryset[:100]
        same_partner_recommendations_queryset = queryset.filter(
            recommended_course__authoring_organizations__in=course.authoring_organizations.all()
        )[:100]

        results = {
            'all_recommendations': serializer_class(all_recommendations_queryset, many=True).data,
            'same_partner_recommendations': serializer_class(same_partner_recommendations_queryset, many=True).data,
        }
        return Response(results)
