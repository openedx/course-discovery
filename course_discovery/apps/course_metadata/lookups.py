from django.db.models import Q
from django.template.loader import render_to_string

from dal import autocomplete
from .models import Course, CourseRun, Organization, Video, Person


class CourseAutocomplete(autocomplete.Select2QuerySetView):
    def get_queryset(self):
        if self.request.user.is_authenticated() and self.request.user.is_staff:
            qs = Course.objects.all()
            if self.q:
                qs = qs.filter(Q(key__icontains=self.q) | Q(title__icontains=self.q))

            return qs

        return []


class CourseRunAutocomplete(autocomplete.Select2QuerySetView):
    def get_queryset(self):
        if self.request.user.is_authenticated() and self.request.user.is_staff:
            qs = CourseRun.objects.all().select_related('course')
            if self.q:
                qs = qs.filter(Q(key__icontains=self.q) | Q(course__title__icontains=self.q))

            return qs

        return []


class OrganizationAutocomplete(autocomplete.Select2QuerySetView):
    def get_queryset(self):
        if self.request.user.is_authenticated() and self.request.user.is_staff:
            qs = Organization.objects.all()

            if self.q:
                qs = qs.filter(Q(key__icontains=self.q) | Q(name__icontains=self.q))

            return qs

        return []


class VideoAutocomplete(autocomplete.Select2QuerySetView):
    def get_queryset(self):
        if self.request.user.is_authenticated() and self.request.user.is_staff:
            qs = Video.objects.all()
            if self.q:
                qs = qs.filter(Q(description__icontains=self.q) | Q(src__icontains=self.q))

            return qs

        return []


class PersonAutocomplete(autocomplete.Select2QuerySetView):
    def get_queryset(self):
        if self.request.user.is_authenticated() and self.request.user.is_staff:
            qs = Person.objects.all()
            if self.q:
                qs = qs.filter(Q(given_name__icontains=self.q) | Q(family_name__icontains=self.q))

            return qs

        return []

    def get_result_label(self, result):
        profile_image = result.profile_image_url
        if hasattr(result.profile_image, 'url'):
            profile_image = result.profile_image.url

        context = {
            'uuid': result.uuid,
            'profile_image': profile_image,
            'full_name': result.full_name,
            'position': result.position if hasattr(result, 'position') else None
        }

        return render_to_string('publisher/_personLookup.html', context=context)
