import uuid

from dal import autocomplete
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db.models import Q
from django.template.loader import render_to_string

from course_discovery.apps.api.serializers import PersonSerializer

from .models import Course, CourseRun, Organization, Person, Program


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

            filter_by_course = self.forwarded.get('course', None)
            if filter_by_course:
                qs = qs.filter(course=filter_by_course)

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


class ProgramAutocomplete(autocomplete.Select2QuerySetView):
    def get_queryset(self):
        if self.request.user.is_authenticated() and self.request.user.is_staff:
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
        org_keys = self.request.GET.getlist('org', None)

        if org_keys:
            # We are pulling the people who are part of course runs belonging to the given organizations.
            # This blank order_by is there to offset the default ordering on people since
            # we don't care about the order in which they are returned.
            queryset = queryset.filter(courses_staffed__course__authoring_organizations__key__in=org_keys).order_by()

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

    def get_result_label(self, result):
        http_referer = self.request.META.get('HTTP_REFERER')
        serialize = self.request.GET.get('serialize')
        if http_referer and '/admin/' in http_referer:
            return super(PersonAutocomplete, self).get_result_label(result)
        elif serialize:
            context = {'request': self.request}
            return PersonSerializer(result, context=context).data
        else:
            context = {
                'uuid': result.uuid,
                'profile_image': result.get_profile_image_url,
                'full_name': result.full_name,
                'position': result.position if hasattr(result, 'position') else None,
                'organization_id': result.position.organization_id if hasattr(result, 'position') else None,
                'can_edit_instructor': not result.get_profile_image_url,

            }

            return render_to_string('publisher/_personLookup.html', context=context)
