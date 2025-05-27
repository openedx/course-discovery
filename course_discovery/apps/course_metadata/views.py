import jwt
import json

from django.contrib import messages
from django.http import Http404, HttpResponseRedirect, JsonResponse
from django.urls import reverse
from django.utils.translation import ugettext_lazy as _
from django.views.generic import TemplateView, UpdateView, View
from edx_rest_api_client.client import EdxRestApiClient

from course_discovery.apps.core.models import Partner
from course_discovery.apps.course_metadata.models import Program
from course_discovery.apps.course_metadata.data_loaders.api import CoursesApiDataLoader


class QueryPreviewView(TemplateView):
    template_name = 'demo/query_preview.html'


class SearchDemoView(TemplateView):
    template_name = 'demo/search.html'


class CourseMetadataRefresher(View):

    def post(self, request):
        """Add a newly created course metadata fetched from LMS into Mysql
            URL: http://0.0.0.0:18000/api/courses/v1/courses/
        """
        response = {}
        data = json.loads(request.body.decode('utf-8'))

        course_id = data.get('course_id')
        if not course_id:
            return JsonResponse({'error': 'Invalid Course Key : {}'.format(course_id)}, status=503)

        try:
            # Get `class Partner` instance by request.site.domain (e.g., 0.0.0.0:18000)
            course_partner = Partner.objects.get(site__domain=request.site.domain)
            access_token, __ = EdxRestApiClient.get_oauth_access_token(
                '{root}/access_token'.format(root=course_partner.oidc_url_root.strip('/')),
                course_partner.oidc_key, course_partner.oidc_secret, token_type='JWT'
            )
            kwargs = {
                'partner': course_partner, 'api_url': course_partner.courses_api_url,
                'access_token': access_token, 'token_type': 'JWT', 'max_workers': 1, 'is_threadsafe': True,
                'course_key': course_id
            }
            username = jwt.decode(access_token, verify=False)['preferred_username']
            if username:
                kwargs['username'] = username

            CoursesApiDataLoader(**kwargs).ingest()

            response[course_partner.short_code] = course_id

        except Exception as e:
            error_message = 'domain: {} | course_key: {} | error: {}'.format(
                request.site.domain, course_id, str(e)
            )

            if 'errors' in response:
                response['errors'].append(error_message)
            else:
                response['errors'] = [error_message]

        return JsonResponse(response)
