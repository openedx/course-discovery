"""
Customize custom views.
"""
from django.core.urlresolvers import reverse
from django.http import Http404, HttpResponseRedirect
from django.views.generic.edit import UpdateView

from course_discovery.apps.publisher_comments.forms import CommentEditForm
from course_discovery.apps.publisher_comments.models import Comments


# pylint: disable=attribute-defined-outside-init
class UpdateCommentView(UpdateView):
    """ Update Comment View."""
    model = Comments
    form_class = CommentEditForm
    template_name = 'comments/edit_comment.html'
    success_url = 'publisher:publisher_seats_edit'

    def get(self, request, *args, **kwargs):
        self.object = self.get_object()
        if request.user != self.object.user:
            raise Http404
        return super(UpdateCommentView, self).get(request, *args, **kwargs)

    def form_valid(self, form):
        self.object = form.save()
        return HttpResponseRedirect(self.get_success_url())

    def get_success_url(self):
        url = reverse('publisher:publisher_seats_edit', kwargs={'pk': self.object.object_pk})
        if self.object.content_type.model == 'seat':
            url = url
        elif self.object.content_type.model == 'course':
            url = reverse('publisher:publisher_courses_edit', kwargs={'pk': self.object.object_pk})
        elif self.object.content_type.model == 'courserun':
            url = reverse('publisher:publisher_course_runs_edit', kwargs={'pk': self.object.object_pk})

        return url
