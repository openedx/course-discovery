from django.db.models import Count
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, render
from django.template.loader import render_to_string
from django.views import View
from django.views.generic import DetailView, ListView

from course_discovery.apps.tagging.mixins import VerticalTaggingAdministratorPermissionRequiredMixin
from course_discovery.apps.tagging.models import Course, CourseVertical, SubVertical, Vertical


class CourseTaggingDetailView(VerticalTaggingAdministratorPermissionRequiredMixin, View):
    """
    Handles displaying course tagging details and assigning verticals and sub-verticals to a course.
    """

    def get(self, request, uuid):
        course = get_object_or_404(Course, uuid=uuid, draft=False)
        verticals = Vertical.objects.all()
        all_sub_verticals = SubVertical.objects.select_related('vertical')
        return render(request, "tagging/course_tagging_detail.html", {
            "course": course,
            "verticals": verticals,
            "all_sub_verticals": all_sub_verticals,
        })

    def post(self, request, uuid):
        course = get_object_or_404(Course, uuid=uuid, draft=False)
        vertical_slug = request.POST.get('vertical')
        sub_vertical_slug = request.POST.get('sub_vertical')

        vertical = Vertical.objects.filter(slug=vertical_slug).first() if vertical_slug else None
        sub_vertical = SubVertical.objects.filter(slug=sub_vertical_slug).first() if sub_vertical_slug else None

        if sub_vertical and sub_vertical.vertical != vertical:
            html = render_to_string("partials/message.html", {
                "error": "Sub-vertical does not belong to the selected vertical."
            }, request)
            return HttpResponse(html, status=200)

        CourseVertical.objects.update_or_create(
            course=course,
            defaults={"vertical": vertical, "sub_vertical": sub_vertical}
        )

        html = render_to_string("partials/message.html", {
            "success": "Vertical and Sub-Vertical assigned successfully."
        }, request)
        return HttpResponse(html, status=200)


class CourseListView(VerticalTaggingAdministratorPermissionRequiredMixin, ListView):
    """
    Renders a list of all Courses with search, sort, and pagination capabilities.
    """
    model = Course
    template_name = "tagging/course_list.html"
    context_object_name = "courses"
    paginate_by = 20

    def get_queryset(self):
        search_query = self.request.GET.get('search', '').strip()
        sort_by = self.request.GET.get('sort', 'title')
        direction = self.request.GET.get('direction', 'asc')

        sort_fields = {
            'key': 'key',
            'title': 'title',
            'vertical': 'product_vertical__vertical__name',
            'sub_vertical': 'product_vertical__sub_vertical__name',
        }
        sort_field = sort_fields.get(sort_by, 'title')
        if direction == 'desc':
            sort_field = f'-{sort_field}'

        queryset = Course.objects.prefetch_related("product_vertical__vertical", "product_vertical__sub_vertical")
        if search_query:
            queryset = queryset.filter(title__icontains=search_query)
        return queryset.order_by(sort_field)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['current_sort'] = self.request.GET.get('sort', 'title')
        context['current_direction'] = self.request.GET.get('direction', 'asc')
        return context

    def render_to_response(self, context, **response_kwargs):
        if self.request.headers.get('HX-Request'):
            course_table_html = render_to_string("partials/course_table.html", context, request=self.request)
            return HttpResponse(course_table_html)
        return super().render_to_response(context, **response_kwargs)


class BaseSortableListView(VerticalTaggingAdministratorPermissionRequiredMixin, ListView):
    """
    Base view to add sorting capabilities for list views.
    """
    default_sort_field = 'name'

    def get_annotated_queryset(self):
        """
        Subclasses should override this method to provide their own annotated queryset.
        """
        raise NotImplementedError("Subclasses must implement `get_annotated_queryset`.")

    def get_queryset(self):
        sort_by = self.request.GET.get('sort', self.default_sort_field)
        direction = self.request.GET.get('direction', 'asc')

        if direction == 'desc':
            sort_by = f'-{sort_by}'

        queryset = self.get_annotated_queryset()
        return queryset.order_by(sort_by)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['current_sort'] = self.request.GET.get('sort', self.default_sort_field)
        context['current_direction'] = self.request.GET.get('direction', 'asc')
        return context


class VerticalListView(BaseSortableListView):
    """
    Renders a list of all Verticals with their assigned courses.
    """
    model = Vertical
    template_name = "tagging/vertical_list.html"
    context_object_name = "verticals"

    def get_annotated_queryset(self):
        return Vertical.objects.annotate(course_count=Count('coursevertical_verticals'))


class SubVerticalListView(BaseSortableListView):
    """
    Renders a list of all SubVerticals with their assigned courses.
    """
    model = SubVertical
    template_name = "tagging/sub_vertical_list.html"
    context_object_name = "sub_verticals"

    def get_annotated_queryset(self):
        return SubVertical.objects.annotate(course_count=Count('coursevertical_sub_verticals'))


class VerticalDetailView(VerticalTaggingAdministratorPermissionRequiredMixin, DetailView):
    """
    Render details of a specific vertical and associated courses.
    """
    model = Vertical
    template_name = "tagging/vertical_detail.html"
    context_object_name = "vertical"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["courses"] = Course.objects.filter(product_vertical__vertical=self.object).distinct()
        return context


class SubVerticalDetailView(VerticalTaggingAdministratorPermissionRequiredMixin, DetailView):
    """
    Render details of a specific sub-vertical and associated courses.
    """
    model = SubVertical
    template_name = "tagging/sub_vertical_detail.html"
    context_object_name = "sub_vertical"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["courses"] = Course.objects.filter(product_vertical__sub_vertical=self.object).distinct()
        return context
