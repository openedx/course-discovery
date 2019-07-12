from dal import autocomplete
from django.db.models import Q

from course_discovery.apps.ietf_language_tags.models import LanguageTag


class LanguageTagAutocomplete(autocomplete.Select2QuerySetView):
    def get_queryset(self):
        if self.request.user.is_authenticated:
            qs = LanguageTag.objects.all()
            if self.q:
                qs = qs.filter(Q(code__icontains=self.q) | Q(name__icontains=self.q))

            return qs

        return []
