'''Filter class for Journals'''
from django_filters import rest_framework as filters

from course_discovery.apps.journal.choices import JournalStatus
from course_discovery.apps.journal.models import Journal


class CharListFilter(filters.CharFilter):
    """ Filters a field via a comma-delimited list of values. """
    def filter(self, qs, value):
        if value not in (None, ''):
            value = value.split(',')

        return super(CharListFilter, self).filter(qs, value)


class JournalFilter(filters.FilterSet):
    status = filters.MultipleChoiceFilter(choices=JournalStatus.choices)
    orgs = CharListFilter(field_name='organization__key', lookup_expr='in')

    class Meta:
        model = Journal
        fields = ('orgs', 'status',)
