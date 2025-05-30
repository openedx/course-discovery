import jwt
import json

from django.http import JsonResponse
from django.views.generic import View
from edx_rest_api_client.client import EdxRestApiClient

from course_discovery.apps.core.models import Partner
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
            # One site, One Partner/Org:
            # Get a `class Partner` instance by the `request.site.domain`(e.g., 0.0.0.0:18000)
            course_site_partner = Partner.objects.get(site__domain=request.site.domain)
            access_token, __ = EdxRestApiClient.get_oauth_access_token(
                '{root}/access_token'.format(root=course_site_partner.oidc_url_root.strip('/')),
                course_site_partner.oidc_key, course_site_partner.oidc_secret, token_type='JWT'
            )
            kwargs = {
                'course_key': target_course_id, 'partner': course_site_partner,
                'api_url': course_site_partner.courses_api_url,
                'access_token': access_token, 'token_type': 'JWT',
                'max_workers': 1, 'is_threadsafe': True
            }
            username = jwt.decode(access_token, verify=False)['preferred_username']
            if username:
                kwargs['username'] = username

            CoursesApiDataLoader(**kwargs).ingest()

            response[course_site_partner.short_code] = target_course_id

        except Exception as e:
            error_message = 'domain: {} | course_key: {} | error: {}'.format(
                request.site.domain, target_course_id, str(e)
            )

            if 'errors' in response:
                response['errors'].append(error_message)
            else:
                response['errors'] = [error_message]

        return JsonResponse(response)
