import uuid

from dal import autocomplete
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db.models import Q

from course_discovery.apps.course_metadata.models import (
    FAQ, Collaborator, CorporateEndorsement, Course, CourseRun, Endorsement, ExpectedLearningItem, JobOutlookItem,
    Organization, Person, Program
)


class CourseAutocomplete(autocomplete.Select2QuerySetView):
    def get_queryset(self):
        if self.request.user.is_authenticated and self.request.user.is_staff:
            qs = Course.objects.all()
            if self.q:
                qs = qs.filter(Q(key__icontains=self.q) | Q(title__icontains=self.q))

            return qs

        return []


class CollaboratorAutocomplete(autocomplete.Select2QuerySetView):
    def get_queryset(self):
        if self.request.user.is_authenticated and self.request.user.is_staff:
            qs = Collaborator.objects.all()
            if self.q:
                qs = qs.filter(Q(name__icontains=self.q) | Q(uuid__icontains=self.q.strip()))

            return qs

        return []


class CorporateEndorsementAutocomplete(autocomplete.Select2QuerySetView):
    def get_queryset(self):
        if self.request.user.is_authenticated and self.request.user.is_staff:
            qs = CorporateEndorsement.objects.all()
            if self.q:
                qs = qs.filter(Q(corporation_name__icontains=self.q) | Q(statement__icontains=self.q))

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


class EndorsementAutocomplete(autocomplete.Select2QuerySetView):
    def get_queryset(self):
        if self.request.user.is_authenticated and self.request.user.is_staff:
            qs = Endorsement.objects.all()
            if self.q:
                qs = qs.filter(quote__icontains=self.q)

            return qs

        return []


class ExpectedLearningItemAutocomplete(autocomplete.Select2QuerySetView):
    def get_queryset(self):
        if self.request.user.is_authenticated and self.request.user.is_staff:
            qs = ExpectedLearningItem.objects.all()
            if self.q:
                qs = qs.filter(value__icontains=self.q)

            return qs

        return []


class FAQAutocomplete(autocomplete.Select2QuerySetView):
    def get_queryset(self):
        if self.request.user.is_authenticated and self.request.user.is_staff:
            qs = FAQ.objects.all()
            if self.q:
                qs = qs.filter(Q(question__icontains=self.q) | Q(answer__icontains=self.q))

            return qs

        return []


class JobOutlookItemAutocomplete(autocomplete.Select2QuerySetView):
    def get_queryset(self):
        if self.request.user.is_authenticated and self.request.user.is_staff:
            qs = JobOutlookItem.objects.all()
            if self.q:
                qs = qs.filter(value__icontains=self.q)

            return qs

        return []


class OrganizationAutocomplete(autocomplete.Select2QuerySetView):
    def get_queryset(self):
        if self.request.user.is_authenticated and self.request.user.is_staff:
            product_source = self.forwarded.get('product_source', None)
            if product_source:
                qs = Organization.objects.filter(organizationmapping__source=product_source)
            else:
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
