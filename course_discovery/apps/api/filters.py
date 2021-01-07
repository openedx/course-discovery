import datetime
import logging

import pytz
from django.contrib.auth import get_user_model
from django.db.models import Q, QuerySet
from django.utils.translation import ugettext as _
from django_filters import rest_framework as filters
from dry_rest_permissions.generics import DRYPermissionFiltersBase
from guardian.shortcuts import get_objects_for_user
from rest_framework.exceptions import NotFound, PermissionDenied

from course_discovery.apps.api.utils import cast2int
from course_discovery.apps.course_metadata.choices import CourseRunStatus, ProgramStatus
from course_discovery.apps.course_metadata.models import (
    Course, CourseEditor, CourseRun, LevelType, Organization, Person, Program, ProgramType, Subject, Topic
)

logger = logging.getLogger(__name__)
User = get_user_model()


class PermissionsFilter(DRYPermissionFiltersBase):
    def filter_list_queryset(self, request, queryset, view):
        """ Filters the list queryset, returning only the objects accessible by the user.

        If a username parameter is passed on the querystring, the filter will will return objects accessible by
        the user corresponding to the given username. NOTE: This functionality is only accessible to staff users.

        Raises:
            PermissionDenied -- If a username querystring parameter is specified, but the user is not a staff user.
            Http404 -- If no User corresponding to the given username exists.

        Returns:
            QuerySet
        """
        perm = queryset.model.get_permission('view')
        user = request.user
        username = request.query_params.get('username', None)

        if username:
            if request.user.is_staff:
                try:
                    user = User.objects.get(username=username)
                except User.DoesNotExist as not_found:
                    raise NotFound(
                        _('No user with the username [{username}] exists.').format(username=username)) from not_found
            else:
                raise PermissionDenied(
                    _('Only staff users are permitted to filter by username. Remove the username parameter.')
                )

        return get_objects_for_user(user, perm)


class CharListFilter(filters.CharFilter):
    """ Filters a field via a comma-delimited list of values. """

    def filter(self, qs, value):
        if value not in (None, ''):
            value = value.split(',')

        return super().filter(qs, value)


class UUIDListFilter(CharListFilter):
    """ Filters a field via a comma-delimited list of UUIDs. """

    def __init__(self, field_name='uuid', label=None, widget=None, method=None, lookup_expr='in', required=False,
                 distinct=False, exclude=False, **kwargs):
        super().__init__(field_name=field_name, label=label, widget=widget, method=method, lookup_expr=lookup_expr,
                         required=required, distinct=distinct, exclude=exclude, **kwargs)


class FilterSetMixin:
    def _apply_filter(self, name, queryset, value):
        return getattr(queryset, name)() if cast2int(value, name) else queryset

    def filter_active(self, queryset, name, value):
        return self._apply_filter(name, queryset, value)

    def filter_marketable(self, queryset, name, value):
        return self._apply_filter(name, queryset, value)


class CourseFilter(filters.FilterSet):
    keys = CharListFilter(field_name='key', lookup_expr='in')
    uuids = UUIDListFilter()
    course_run_statuses = CharListFilter(method='filter_by_course_run_statuses')
    editors = CharListFilter(field_name='editors__user__pk', lookup_expr='in', distinct=True)

    class Meta:
        model = Course
        fields = ('keys', 'uuids',)

    def filter_by_course_run_statuses(self, queryset, _, value):
        statuses = set(value.split(','))
        or_queries = []  # a list of Q() expressions to add to our filter as alternatives to status check

        if 'in_review' in statuses:  # any of our review statuses
            statuses.remove('in_review')
            statuses.add(CourseRunStatus.LegalReview)
            statuses.add(CourseRunStatus.InternalReview)
        if 'unsubmitted' in statuses:  # unpublished and unarchived
            statuses.remove('unsubmitted')
            # "is not archived" logic stolen from CourseRun.has_ended
            now = datetime.datetime.now(pytz.UTC)
            or_queries.append(Q(course_runs__status=CourseRunStatus.Unpublished) & ~Q(course_runs__end__lt=now))

        status_check = Q(course_runs__status__in=statuses)
        for query in or_queries:
            status_check |= query

        return queryset.filter(status_check, course_runs__hidden=False).distinct()


class CourseRunFilter(FilterSetMixin, filters.FilterSet):
    active = filters.BooleanFilter(method='filter_active')
    marketable = filters.BooleanFilter(method='filter_marketable')
    keys = CharListFilter(field_name='key', lookup_expr='in')
    license = filters.CharFilter(field_name='license', lookup_expr='iexact')

    @property
    def qs(self):
        # This endpoint supports query via Haystack. If that form of filtering is active,
        # do not attempt to treat the queryset as a normal Django queryset.
        if not isinstance(self.queryset, QuerySet):
            return self.queryset

        return super().qs

    class Meta:
        model = CourseRun
        fields = ('keys', 'hidden', 'license',)


class ProgramFilter(FilterSetMixin, filters.FilterSet):
    marketable = filters.BooleanFilter(method='filter_marketable')
    status = filters.MultipleChoiceFilter(choices=ProgramStatus.choices)
    type = filters.CharFilter(field_name='type__translations__name_t', lookup_expr='iexact')
    types = CharListFilter(field_name='type__slug', lookup_expr='in')
    uuids = UUIDListFilter()

    class Meta:
        model = Program
        fields = ('hidden', 'marketable', 'marketing_slug', 'status', 'type', 'types',)


class ProgramTypeFilter(filters.FilterSet):
    language_code = filters.CharFilter(method='_set_language')

    def _set_language(self, queryset, _, language_code):
        return queryset.language(language_code)

    class Meta:
        model = ProgramType
        fields = ('language_code',)


class LevelTypeFilter(filters.FilterSet):
    language_code = filters.CharFilter(method='_set_language')

    def _set_language(self, queryset, _, language_code):
        return queryset.language(language_code)

    class Meta:
        model = LevelType
        fields = ('language_code',)


class OrganizationFilter(filters.FilterSet):
    tags = CharListFilter(field_name='tags__name', lookup_expr='in')
    uuids = UUIDListFilter()

    class Meta:
        model = Organization
        fields = ('tags', 'uuids',)


class PersonFilter(filters.FilterSet):
    class Meta:
        model = Person
        fields = ('slug',)


class SubjectFilter(filters.FilterSet):
    language_code = filters.CharFilter(method='_set_language')

    def _set_language(self, queryset, _, language_code):
        return queryset.language(language_code)

    class Meta:
        model = Subject
        fields = ('slug', 'language_code')


class TopicFilter(filters.FilterSet):
    language_code = filters.CharFilter(method='_set_language')

    def _set_language(self, queryset, _, language_code):
        return queryset.language(language_code)

    class Meta:
        model = Topic
        fields = ('slug', 'language_code')


class CourseEditorFilter(filters.FilterSet):
    course = filters.CharFilter(field_name='course__uuid')

    class Meta:
        model = CourseEditor
        fields = ('course',)
