import uuid

from dal import autocomplete
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db.models import Q

from .models import Course, CourseRun, Organization, Person, Program


class CourseAutocomplete(autocomplete.Select2QuerySetView):
    def get_queryset(self):
        if self.request.user.is_authenticated and self.request.user.is_staff:
            qs = Course.objects.all()
            if self.q:
                qs = qs.filter(Q(key__icontains=self.q) | Q(title__icontains=self.q))

            return qs

        return []


class CourseRunAutocomplete(autocomplete.Select2QuerySetView):
    def get_queryset(self):
        if self.request.user.is_authenticated and self.request.user.is_staff:
            qs = CourseRun.objects.all().select_related('course')

            filter_by_course = self.forwarded.get('course', None)
            if filter_by_course:
                qs = qs.filter(course=filter_by_course)

            if self.q:
                qs = qs.filter(Q(key__icontains=self.q) | Q(course__title__icontains=self.q))

            return qs

        return []


class OrganizationAutocomplete(autocomplete.Select2QuerySetView):
    def get_queryset(self):
        if self.request.user.is_authenticated and self.request.user.is_staff:
            qs = Organization.objects.all()

            if self.q:
                qs = qs.filter(Q(key__icontains=self.q) | Q(name__icontains=self.q))

            return qs

        return []


class ProgramAutocomplete(autocomplete.Select2QuerySetView):
    def get_queryset(self):
        if self.request.user.is_authenticated and self.request.user.is_staff:
            qs = Program.objects.all()

            if self.q:
                qs = qs.filter(title__icontains=self.q)

            return qs

        return []


class PersonAutocomplete(LoginRequiredMixin, autocomplete.Select2QuerySetView):
    def get_queryset(self):
        words = self.q and self.q.split()
        if not words:
            return []

        # Match each word separately
        queryset = Person.objects.all()

        for word in words:
            # Progressively filter the same queryset - every word must match something
            queryset = queryset.filter(Q(given_name__icontains=word) | Q(family_name__icontains=word))

        # No match? Maybe they gave us a UUID...
        if not queryset:
            try:
                q_uuid = uuid.UUID(self.q).hex
                queryset = Person.objects.filter(uuid=q_uuid)
            except ValueError:
                pass

        return queryset
