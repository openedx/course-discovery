from django.contrib import admin, messages
from django.contrib.auth import get_permission_codename
from django.http import Http404, HttpResponseRedirect
from django.shortcuts import render
from django.urls import reverse
from django.utils.translation import ugettext_lazy as _
from django.views.generic import TemplateView, UpdateView, View
from taxonomy.utils import (
    blacklist_course_skill, get_blacklisted_course_skills, get_whitelisted_course_skills,
    remove_course_skill_from_blacklist
)

from course_discovery.apps.course_metadata.forms import CourseRunSelectionForm, ExcludeSkillsForm
from course_discovery.apps.course_metadata.models import Course, Program


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
            context = super().get_context_data(**kwargs)
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


class CourseSkillsView(View):
    """
    Course Skills view.

    For displaying course skills of a particular course.
    """
    template = 'admin/course_metadata/course_skills.html'
    form = ExcludeSkillsForm

    class ContextParameters:
        """
        Namespace-style class for custom context parameters.
        """
        EXCLUDED_SKILLS = 'excluded_skills'
        COURSE_SKILLS = 'course_skills'
        COURSE = 'course'

    @staticmethod
    def _get_admin_context(request, course):
        """
        Build admin context.
        """
        opts = course._meta
        codename = get_permission_codename('change', opts)
        has_change_permission = request.user.has_perm('%s.%s' % (opts.app_label, codename))
        return {
            'has_change_permission': has_change_permission,
            'opts': opts
        }

    def _get_view_context(self, course_pk):
        """
        Return the default context parameters.
        """
        course = Course.objects.get(id=course_pk)
        course_skills = get_whitelisted_course_skills(course.key)
        excluded_skills = get_blacklisted_course_skills(course.key)
        return {
            self.ContextParameters.COURSE: course,
            self.ContextParameters.COURSE_SKILLS: course_skills,
            self.ContextParameters.EXCLUDED_SKILLS: excluded_skills,
        }

    def _build_context(self, request, course_pk):
        """
        Build admin and view context used by the template.
        """
        context = self._get_view_context(course_pk)
        context.update(admin.site.each_context(request))
        context.update(self._get_admin_context(request, context['course']))
        return context

    def get(self, request, course_pk):
        """
        Handle GET request - renders the template.

        Arguments:
            request (django.http.request.HttpRequest): Request instance
            course_pk (str): Primary key of the course

        Returns:
            django.http.response.HttpResponse: HttpResponse
        """
        context = self._build_context(request, course_pk)
        context['exclude_skills_form'] = self.form(
            context[self.ContextParameters.COURSE_SKILLS],
            context[self.ContextParameters.EXCLUDED_SKILLS],
        )

        return render(request, self.template, context)

    def post(self, request, course_pk):
        """
        Handle POST request - saves excluded/included skills.

        Arguments:
            request (django.http.request.HttpRequest): Request instance
            course_pk (str): Primary key of the course

        Returns:
            django.http.response.HttpResponse: HttpResponse
        """
        course = Course.objects.get(id=course_pk)
        course_skills = get_whitelisted_course_skills(course.key)
        excluded_skills = get_blacklisted_course_skills(course.key)

        form = self.form(course_skills, excluded_skills, data=request.POST)
        if form.is_valid():
            for skill_id in form.cleaned_data['exclude_skills']:
                blacklist_course_skill(course.key, skill_id)

            for skill_id in form.cleaned_data['include_skills']:
                remove_course_skill_from_blacklist(course.key, skill_id)

        context = self._build_context(request, course_pk)
        context['exclude_skills_form'] = self.form(
            context[self.ContextParameters.COURSE_SKILLS],
            context[self.ContextParameters.EXCLUDED_SKILLS],
        )

        return render(request, self.template, context)
