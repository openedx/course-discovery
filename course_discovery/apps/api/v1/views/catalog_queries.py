import logging
from uuid import UUID

from elasticsearch_dsl.query import Q as ESDSLQ
from rest_framework import status
from rest_framework.generics import GenericAPIView
from rest_framework.permissions import DjangoModelPermissions, IsAuthenticated
from rest_framework.response import Response

from course_discovery.apps.api.mixins import ValidElasticSearchQueryRequiredMixin
from course_discovery.apps.course_metadata.models import Course, CourseRun

log = logging.getLogger(__name__)


class CatalogQueryContainsViewSet(ValidElasticSearchQueryRequiredMixin, GenericAPIView):
    permission_classes = (IsAuthenticated, DjangoModelPermissions)
    queryset = Course.objects.all()

    def get(self, request):
        """
        Determine if a set of courses and/or course runs is found in the query results.

        Returns
            dict:  mapping of course and run identifiers included in the request to boolean values
                indicating whether the associated course or run is contained in the queryset
                described by the query found in the request.
        """
        query = request.GET.get('query')
        course_run_ids = request.GET.get('course_run_ids', None)
        course_uuids = request.GET.get('course_uuids', None)
        partner = self.request.site.partner

        if query and (course_run_ids or course_uuids):
            log.info(
                f"Attempting search against query {query} with course UUIDs {course_uuids} "
                f"and course run IDs {course_run_ids}"
            )
            identified_course_ids = set()
            specified_course_ids = []
            if course_run_ids:
                course_run_ids = course_run_ids.split(',')
                specified_course_ids = course_run_ids
                identified_course_ids.update(
                    i.key
                    for i in CourseRun.search(query)
                    .filter(ESDSLQ('term', partner=partner.short_code) & ESDSLQ('terms', **{'key.raw': course_run_ids}))
                    .source(['key'])
                )
            if course_uuids:
                course_uuids = [UUID(course_uuid) for course_uuid in course_uuids.split(',')]
                specified_course_ids += course_uuids

                log.info(f"Specified course ids: {specified_course_ids}")
                identified_course_ids.update(
                    Course.search(query).filter(partner=partner, uuid__in=course_uuids).values_list('uuid', flat=True)
                )
            log.info(f"Identified {len(identified_course_ids)} course ids: {identified_course_ids}")

            contains = {str(identifier): identifier in identified_course_ids for identifier in specified_course_ids}
            return Response(contains)
        return Response(
            'CatalogQueryContains endpoint requires query and identifiers list(s)', status=status.HTTP_400_BAD_REQUEST
        )
