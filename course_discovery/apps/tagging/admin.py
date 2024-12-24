import csv

from django.contrib import admin, messages
from django.shortcuts import redirect, render
from django.urls import reverse

from course_discovery.apps.course_metadata.models import Course
from course_discovery.apps.tagging.forms import CSVUploadForm
from course_discovery.apps.tagging.models import CourseVerticalFilters, SubVericalFilter, VerticalFilter, ProgramVericalFilters, VerticalFilterTags


@admin.register(VerticalFilter)
class VerticalFilterAdmin(admin.ModelAdmin):
    """
    Admin class for VerticalFilter model.
    """
    list_display = ('name', 'is_active', 'description', 'slug',)
    search_fields = ('name',)


@admin.register(SubVericalFilter)
class SubVericalFilterAdmin(admin.ModelAdmin):
    """
    Admin class for SubVerticalFilter model.
    """
    list_display = ('name', 'is_active', 'slug', 'description', 'vertical_filters')
    list_filter = ('vertical_filters', )
    search_fields = ('name',)
    ordering = ('name',)


@admin.register(CourseVerticalFilters)
class CourseVerticalFiltersAdmin(admin.ModelAdmin):
    """
    Admin class for CourseVerticalFilters model.
    """
    list_display = ('course', 'vertical', 'sub_vertical')
    list_filter = ('vertical', 'sub_vertical')
    search_fields = ('course__title', 'vertical__name', 'sub_vertical__name')
    ordering = ('course__title',)

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        """
        Override the formfield_for_foreignkey method to filter the course field based on draft status.
        """
        if db_field.name == 'course':
            kwargs['queryset'] = Course.objects.filter(draft=False)
        return super().formfield_for_foreignkey(db_field, request, **kwargs)

    def changelist_view(self, request, extra_context=None):
        """
        Override the changelist_view method to add a custom upload CSV button.
        """
        extra_context = extra_context or {}
        extra_context['upload_csv_url'] = reverse('admin:courseverticalfilters_upload_csv')
        return super().changelist_view(request, extra_context=extra_context)

    def get_urls(self):
        """
        Override the get_urls method to add a custom upload CSV URL.
        """
        from django.urls import path
        urls = super().get_urls()
        custom_urls = [
            path('upload-csv/', self.upload_csv, name='courseverticalfilters_upload_csv'),
        ]
        return custom_urls + urls

    def upload_csv(self, request):
        """
        Custom view to upload a CSV file and process it to update the course vertical filters to support bulk updates.
        """
        if request.method == 'POST' and request.FILES.get('csv_file'):
            form = CSVUploadForm(request.POST, request.FILES)
            if form.is_valid():
                csv_file = form.cleaned_data['csv_file']
                try:
                    decoded_file = csv_file.read().decode('utf-8').splitlines()
                    reader = csv.reader(decoded_file)
                    next(reader)  # Skip the header row
                    for row in reader:
                        course_key = row[0]
                        vertical_name = row[1]
                        sub_vertical_name = row[2]

                        course = Course.objects.get(key=course_key)
                        vertical, _ = VerticalFilter.objects.get_or_create(name=vertical_name)
                        sub_vertical, _ = SubVericalFilter.objects.get_or_create(
                            name=sub_vertical_name, vertical_filters=vertical
                        )

                        CourseVerticalFilters.objects.update_or_create(
                            course=course,
                            defaults={'vertical': vertical, 'sub_vertical': sub_vertical}
                        )

                    messages.success(request, "CSV uploaded and processed successfully.")
                except Exception as e:
                    messages.error(request, f"Error processing CSV: {str(e)}")
                return redirect('admin:tagging_courseverticalfilters_changelist')
        else:
            form = CSVUploadForm()

        return render(
            request,
            'admin/tagging/courseverticalfilters/upload_csv_form.html',
            context={'form': form}
        )

@admin.register(ProgramVericalFilters)
class ProgramVericalFiltersAdmin(admin.ModelAdmin):
    """
    Admin class for Program Vertical Filters model.
    """
    list_display = ('program', 'vertical', 'sub_vertical')
    list_filter = ('vertical', 'sub_vertical')
    search_fields = ('program__title', 'vertical__name', 'sub_vertical__name')
    ordering = ('program__title',)

@admin.register(VerticalFilterTags)
class VerticalFilterTagsAdmin(admin.ModelAdmin):
    """
    Admin class for VerticalFilterTags model.
    """
    list_display = ('content_type', 'object_id', 'vertical', 'sub_vertical')
    list_filter = ('vertical', 'sub_vertical', 'content_type')
    search_fields = ('object_id', )
