import jwt
import json

from django.contrib import messages
from django.http import Http404, HttpResponseRedirect, JsonResponse
from django.urls import reverse
from django.utils.translation import ugettext_lazy as _
from django.views.generic import TemplateView, UpdateView, View
from edx_rest_api_client.client import EdxRestApiClient

from course_discovery.apps.core.models import Partner
from course_discovery.apps.course_metadata.forms import CourseRunSelectionForm
from course_discovery.apps.course_metadata.models import Program
from course_discovery.apps.course_metadata.data_loaders.api import CoursesApiDataLoader


class QueryPreviewView(TemplateView):
    template_name = 'demo/query_preview.html'


class SearchDemoView(TemplateView):
    template_name = 'demo/search.html'


# pylint: disable=attribute-defined-outside-init
class CourseRunSelectionAdmin(UpdateView):
    """ Create Course View."""
    model = Program
    template_name = 'admin/course_metadata/course_run.html'
    form_class = CourseRunSelectionForm

    def get_context_data(self, **kwargs):
        if self.request.user.is_authenticated() and self.request.user.is_staff:
            context = super(CourseRunSelectionAdmin, self).get_context_data(**kwargs)
            context.update({
                'program_id': self.object.id,
                'title': _('Update excluded course runs')
            })
            return context
        raise Http404

    def form_valid(self, form):
        self.object = form.save()
        message = _('The program was changed successfully.')
        messages.add_message(self.request, messages.SUCCESS, message)
        return HttpResponseRedirect(self.get_success_url())

    def get_success_url(self):
        return reverse('admin:course_metadata_program_change', args=(self.object.id,))


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

        partner_code = data.get('partner_code', None)
        # If a specific partner was indicated, filter down the set
        partners = Partner.filter(short_code=partner_code) if partner_code else Partner.objects.all()
        if not partners:
            return JsonResponse({'error': 'No partners available!'}, status=503)

        for partner in partners:
            try:
                access_token, __ = EdxRestApiClient.get_oauth_access_token(
                    '{root}/access_token'.format(root=partner.oidc_url_root.strip('/')),
                    partner.oidc_key, partner.oidc_secret, token_type='JWT'
                )
                kwargs = {
                    'partner': partner, 'api_url': partner.courses_api_url, 'access_token': access_token,
                    'token_type': 'JWT', 'max_workers': 1, 'is_threadsafe': True, 'course_key': course_id
                }
                username = jwt.decode(access_token, verify=False)['preferred_username']
                if username:
                    kwargs['username'] = username

                CoursesApiDataLoader(**kwargs).ingest()

                response[partner.short_code] = course_id

            except Exception as e:
                error_message = 'code: {} | course_key: {} | error: {}'.format(
                    partner.short_code, course_id, str(e)
                )

                if 'errors' in response:
                    response['errors'].append(error_message)
                else:
                    response['errors'] = error_message

        return JsonResponse(response)
