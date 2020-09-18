from uuid import UUID

from rest_framework import status
from rest_framework.generics import GenericAPIView
from rest_framework.permissions import DjangoModelPermissions, IsAuthenticated
from rest_framework.response import Response

from course_discovery.apps.course_metadata.models import Course, CourseRun


class CatalogQueryContainsViewSet(GenericAPIView):
    permission_classes = (IsAuthenticated, DjangoModelPermissions)
    queryset = Course.objects.all()

    def get(self, request):
        """
        Determine if a set of courses and/or course runs is found in the query results.

        Returns
            dict:  mapping of course and run indentifiers included in the request to boolean values
                indicating whether or not the associated course or run is contained in the queryset
                described by the query found in the request.
        """
        query = request.GET.get('query')
        course_run_ids = request.GET.get('course_run_ids', None)
        course_uuids = request.GET.get('course_uuids', None)
        partner = self.request.site.partner

        if query and (course_run_ids or course_uuids):
            identified_course_ids = set()
            specified_course_ids = []
            if course_run_ids:
                course_run_ids = course_run_ids.split(',')
                specified_course_ids = course_run_ids
                identified_course_ids.update(CourseRun.search(query).filter(
                    partner=partner.short_code, key__in=course_run_ids).values_list('key', flat=True))
            if course_uuids:
                course_uuids = [UUID(course_uuid) for course_uuid in course_uuids.split(',')]
                specified_course_ids += course_uuids
                identified_course_ids.update(Course.search(query).filter(partner=partner, uuid__in=course_uuids).
                                             values_list('uuid', flat=True))

            contains = {str(identifier): identifier in identified_course_ids for identifier in specified_course_ids}
            return Response(contains)
        return Response(
            'CatalogQueryContains endpoint requires query and identifiers list(s)', status=status.HTTP_400_BAD_REQUEST
        )
