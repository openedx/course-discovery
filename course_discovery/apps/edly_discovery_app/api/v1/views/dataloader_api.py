"""
Views for Dataloader API.
"""
import logging

from opaque_keys.edx.keys import CourseKey
from rest_framework import status
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView

from course_discovery.apps.course_metadata.data_loaders.api import (
    CoursesApiDataLoader,
    EcommerceApiDataLoader,
    WordPressApiDataLoader,
)
from course_discovery.apps.core.models import Partner

logger = logging.getLogger(__name__)


class EdlyDataLoaderView(APIView):
    """
    Refresh course metadata from external sources.
    """
    permission_classes = [IsAuthenticated, ]

    def post(self, request):
        """
        Loads and updates course runs from the given service.
        """
        raw_data = request.POST.copy()
        partner = raw_data.get('partner')
        course_id = raw_data.get('course_id')
        service = raw_data.get('service')
        if not any([partner, course_id, service]):
            return Response(
                {'error': 'Missing information'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            partner = Partner.objects.get(short_code=partner)
        except Partner.DoesNotExist:
            return Response(
                {'error': 'Partner does not exist'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        try:
            CourseKey.from_string(course_id)
        except:
            return Response(
                {'error': 'Course id is not valid.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        pipeline = {
            'lms': (CoursesApiDataLoader, partner.courses_api_url),
            'ecommerce': (EcommerceApiDataLoader, partner.ecommerce_api_url),
            'wordpress': (WordPressApiDataLoader, partner.marketing_site_api_url),
        }

        loader = pipeline.get(service)
        if not loader:
            return Response(
                {'error': 'Data Loader for service: {} is not handled by API'.format(
                    service)},
                status=status.HTTP_400_BAD_REQUEST,
            )

        dataloader, api_url = loader
        logger.info('Executing Loader [{}]'.format(api_url))
        dataloader(
            partner=partner,
            api_url=api_url,
            max_workers=1,
            course_id=course_id
        ).ingest()

        return Response(
            {'message': "Course Sync'd with {}".format(service)},
            status=status.HTTP_200_OK,
        )
