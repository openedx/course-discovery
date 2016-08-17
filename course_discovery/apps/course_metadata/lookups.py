from django.db.models import Q

from dal import autocomplete
from .models import Course, Organization, Video


class CourseAutocomplete(autocomplete.Select2QuerySetView):
    def get_queryset(self):
        if self.request.user.is_authenticated() and self.request.user.is_staff:
            qs = Course.objects.all()
            if self.q:
                qs = qs.filter(Q(key__icontains=self.q) | Q(title__icontains=self.q))

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
