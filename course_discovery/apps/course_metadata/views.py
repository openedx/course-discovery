from django.contrib import messages
from django.http import Http404, HttpResponseRedirect
from django.urls import reverse
from django.utils.translation import ugettext_lazy as _
from django.views.generic import TemplateView, UpdateView

from course_discovery.apps.course_metadata.forms import CourseRunSelectionForm
from course_discovery.apps.course_metadata.models import Program


class QueryPreviewView(TemplateView):
    template_name = 'demo/query_preview.html'


# pylint: disable=attribute-defined-outside-init
class CourseRunSelectionAdmin(UpdateView):
    """ Create Course View."""
    model = Program
    template_name = 'admin/course_metadata/course_run.html'
    form_class = CourseRunSelectionForm

    def get_context_data(self, **kwargs):
        if self.request.user.is_authenticated and self.request.user.is_staff:
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
