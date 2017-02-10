from dal import autocomplete

from course_discovery.apps.core.models import User


class UserAutocomplete(autocomplete.Select2QuerySetView):
    def get_queryset(self):
        if self.request.user.is_authenticated() and self.request.user.is_staff:
            qs = User.objects.all()
            if self.q:
                qs = qs.filter(username__icontains=self.q)

            return qs

        return []
