import csv
from io import TextIOWrapper

from django.contrib import admin, messages
from django.shortcuts import redirect, render
from django.template.response import TemplateResponse
from django.urls import reverse

from course_discovery.apps.course_metadata.models import Course
from course_discovery.apps.tagging.forms import CSVUploadForm
from course_discovery.apps.tagging.models import (
    CourseVerticalFilters, ProgramVerticalFilters, SubVericalFilter, VerticalFilter
)


@admin.register(VerticalFilter)
class VerticalFilterAdmin(admin.ModelAdmin):
    list_display = ('name', 'is_active', 'description', 'slug',)
    search_fields = ('name',)

    def changelist_view(self, request, extra_context=None):
        extra_context = extra_context or {}
        extra_context['upload_csv_url'] = reverse('admin:verticalfilter_upload_csv')
        return super().changelist_view(request, extra_context=extra_context)

    def get_urls(self):
        from django.urls import path
        urls = super().get_urls()
        custom_urls = [
            path(
                'upload-csv/',
                self.admin_site.admin_view(self.upload_csv),
                name='verticalfilter_upload_csv',
            ),
        ]
        return custom_urls + urls

    def upload_csv(self, request):
        from django.shortcuts import redirect
        if request.method == 'POST' and request.FILES.get('csv_file'):
            csv_file = request.FILES['csv_file']
            file_data = TextIOWrapper(csv_file, encoding='utf-8')
            csv_reader = csv.reader(file_data)

            # Skipping the header row
            next(csv_reader)

            created_count = 0
            for row in csv_reader:
                # Assuming the CSV structure is [name, description, is_active]
                if row:  # Skip empty rows
                    name, description, is_active = row
                    try:
                        # Create a VerticalFilter instance for each row
                        VerticalFilter.objects.create(
                            name=name,
                            description=description,
                            is_active=(is_active.lower() == 'true'),  # Assuming 'true' or 'false' in CSV
                        )
                        created_count += 1
                    except Exception as e:
                        # Log the error or handle invalid rows
                        messages.error(request, f"Error processing row: {row}. Error: {e}")
            
            messages.success(request, f"{created_count} VerticalFilter instances created successfully!")
            return redirect('admin:tagging_verticalfilter_changelist')

        return TemplateResponse(
            request,
            "admin/tagging/verticalfilter/upload_csv_form.html",
            context={'opts': self.model._meta},
        )


@admin.register(SubVericalFilter)
class SubVericalFilterAdmin(admin.ModelAdmin):
    list_display = ('name', 'is_active', 'slug', 'description', 'vertical_filters')
    list_filter = ('vertical_filters', )
    search_fields = ('name',)
    ordering = ('name',)


@admin.register(CourseVerticalFilters)
class CourseVerticalFiltersAdmin(admin.ModelAdmin):
    list_display = ('course', 'vertical', 'sub_vertical')
    list_filter = ('vertical', 'sub_vertical')
    search_fields = ('course__title', 'vertical__name', 'sub_vertical__name')
    ordering = ('course__title',)
    
    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        if db_field.name == 'course':
            kwargs['queryset'] = Course.objects.filter(draft=False)
        return super().formfield_for_foreignkey(db_field, request, **kwargs)
    
    def changelist_view(self, request, extra_context=None):
        extra_context = extra_context or {}
        extra_context['upload_csv_url'] = reverse('admin:courseverticalfilters_upload_csv')
        return super().changelist_view(request, extra_context=extra_context)

    
    def get_urls(self):
        from django.urls import path
        urls = super().get_urls()
        custom_urls = [
            path('upload-csv/', self.upload_csv, name='courseverticalfilters_upload_csv'),
        ]
        return custom_urls + urls

    # Handle the CSV upload
    def upload_csv(self, request):
        if request.method == 'POST' and request.FILES.get('csv_file'):
            form = CSVUploadForm(request.POST, request.FILES)
            if form.is_valid():
                # Process the CSV file
                csv_file = form.cleaned_data['csv_file']
                try:
                    decoded_file = csv_file.read().decode('utf-8').splitlines()
                    reader = csv.reader(decoded_file)
                    next(reader)  # Skip the header row
                    for row in reader:
                        course_uuid = row[0]  # Assuming the first column is the course title
                        vertical_name = row[1]  # Assuming the second column is the vertical name
                        sub_vertical_name = row[2]  # Assuming the third column is the sub-vertical name

                        # Get the corresponding objects from the database
                        import pdb; pdb.set_trace();
                        course = Course.objects.get(uuid=course_uuid)
                        vertical, _ = VerticalFilter.objects.get_or_create(name=vertical_name)
                        sub_vertical, _ = SubVericalFilter.objects.get_or_create(name=sub_vertical_name, vertical_filters=vertical)

                        # Create or update the CourseVerticalFilters instance
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
            'admin/tagging/courseverticalfilters/upload_csv_form.html',  # You can create a custom template for the upload form
            context={'form': form}
        )


@admin.register(ProgramVerticalFilters)
class ProgramVerticalFiltersAdmin(admin.ModelAdmin):
    list_display = ('program', 'vertical', 'sub_vertical')
    list_filter = ('vertical', 'sub_vertical')
    search_fields = ('program__title', 'vertical__name', 'sub_vertical__name')
    ordering = ('program__title',)
