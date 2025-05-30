import logging

from django.contrib.auth import get_user_model
from django.db.models import QuerySet
from django_filters import rest_framework as filters

from course_discovery.apps.api.utils import cast2int
from course_discovery.apps.course_metadata.choices import ProgramStatus
from course_discovery.apps.course_metadata.models import (
    Course, CourseRun, Program
)


logger = logging.getLogger(__name__)
User = get_user_model()


class CharListFilter(filters.CharFilter):
    """ Filters a field via a comma-delimited list of values. """

    def filter(self, qs, value):  # pylint: disable=method-hidden
        if value not in (None, ''):
            value = value.split(',')

        return super(CharListFilter, self).filter(qs, value)


class UUIDListFilter(CharListFilter):
    """ Filters a field via a comma-delimited list of UUIDs. """

    def __init__(self, name='uuid', label=None, widget=None, method=None, lookup_expr='in', required=False,
                 distinct=False, exclude=False, **kwargs):
        super().__init__(name=name, label=label, widget=widget, method=method, lookup_expr=lookup_expr,
                         required=required, distinct=distinct, exclude=exclude, **kwargs)


class FilterSetMixin:
    def _apply_filter(self, name, queryset, value):
        return getattr(queryset, name)() if cast2int(value, name) else queryset

    def filter_active(self, queryset, name, value):
        return self._apply_filter(name, queryset, value)

    def filter_marketable(self, queryset, name, value):
        return self._apply_filter(name, queryset, value)


class CourseFilter(filters.FilterSet):
    keys = CharListFilter(name='key', lookup_expr='in')
    uuids = UUIDListFilter()

    class Meta:
        model = Course
        fields = ('keys', 'uuids',)


class CourseRunFilter(FilterSetMixin, filters.FilterSet):
    active = filters.BooleanFilter(method='filter_active')
    marketable = filters.BooleanFilter(method='filter_marketable')
    keys = CharListFilter(name='key', lookup_expr='in')

    @property
    def qs(self):
        # This endpoint supports query via Haystack. If that form of filtering is active,
        # do not attempt to treat the queryset as a normal Django queryset.
        if not isinstance(self.queryset, QuerySet):
            return self.queryset

        return super(CourseRunFilter, self).qs

    class Meta:
        model = CourseRun
        fields = ('keys',)


class ProgramFilter(FilterSetMixin, filters.FilterSet):
    status = filters.MultipleChoiceFilter(choices=ProgramStatus.choices)
    uuids = UUIDListFilter()

    class Meta:
        model = Program
        fields = ('status',)
