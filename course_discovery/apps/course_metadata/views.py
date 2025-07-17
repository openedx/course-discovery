import jwt
import json

from django.conf import settings
from django.http import JsonResponse
from django.views.generic import View

from edx_rest_api_client.client import EdxRestApiClient

from course_discovery.apps.course_metadata.data_loaders.api import CoursesApiDataLoader


class CourseMetadataRefresher(View):

    def post(self, request):
        """Add a newly created course metadata fetched from LMS into Mysql
            URL: http://0.0.0.0:18000/api/courses/v1/courses/
        """
        response = {}
        data = json.loads(request.body.decode('utf-8'))

        target_course_id = data.get('course_id')
        if not target_course_id:
            return JsonResponse(
                {'error': 'Invalid Course Key : {}'.format(target_course_id)}, status=503
            )

        try:
            partner = getattr(settings, 'PARTNER', None)
            prefix = 'https://' if partner.get('IS_SECURE', True) else 'http://'

            courses_api_url = '{prefix}{lms_domain}{end_point}'.format(
                prefix=prefix,
                lms_domain=request.site.domain,
                end_point=partner['COURSES_API_URL']
            )
            oidc_url_root = '{prefix}{lms_domain}{end_point}'.format(
                prefix=prefix,
                lms_domain=request.site.domain,
                end_point=partner['OIDC_URL_ROOT']
            ).strip('/')

            access_token, __ = EdxRestApiClient.get_oauth_access_token(
                '{root}/access_token'.format(root=oidc_url_root),
                partner['OIDC_KEY'],
                partner['OIDC_SECRET'],
                token_type='JWT'
            )
            kwargs = {
                'course_key': target_course_id,
                'partner': partner,
                'api_url': courses_api_url,
                'access_token': access_token,
                'token_type': 'JWT',
                'max_workers': 1,
                'is_threadsafe': True
            }
            username = jwt.decode(access_token, verify=False)['preferred_username']
            if username:
                kwargs['username'] = username

            CoursesApiDataLoader(**kwargs).ingest()

            response['course_key'] = target_course_id

        except Exception as e:
            error_message = 'domain: {} | course_key: {} | error: {}'.format(
                request.site.domain, target_course_id, str(e)
            )

            if 'errors' in response:
                response['errors'].append(error_message)
            else:
                response['errors'] = [error_message]

        return JsonResponse(response)
