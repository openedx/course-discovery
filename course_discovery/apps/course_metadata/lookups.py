import uuid

from dal import autocomplete
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db.models import Q
from django.template.loader import render_to_string

from .models import Course, CourseRun, Organization, Person


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


class PersonAutocomplete(LoginRequiredMixin, autocomplete.Select2QuerySetView):
    def get_queryset(self):
        queryset = Person.objects.all()
        if self.q:
            qs = queryset.filter(Q(given_name__icontains=self.q) | Q(family_name__icontains=self.q))

            if not qs:
                try:
                    q_uuid = uuid.UUID(self.q).hex
                    qs = queryset.filter(uuid=q_uuid)
                except ValueError:
                    pass

            return qs

        return []

    def get_result_label(self, result):
        http_referer = self.request.META.get('HTTP_REFERER')
        if http_referer and '/admin/' in http_referer:
            return super(PersonAutocomplete, self).get_result_label(result)
        else:
            context = {
                'uuid': result.uuid,
                'profile_image': result.get_profile_image_url,
                'full_name': result.full_name,
                'position': result.position if hasattr(result, 'position') else None
            }

            return render_to_string('publisher/_personLookup.html', context=context)
