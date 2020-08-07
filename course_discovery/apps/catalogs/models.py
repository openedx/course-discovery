from collections.abc import Iterable

from django.db import models
from django.utils.translation import ugettext_lazy as _
from django_extensions.db.models import TimeStampedModel
from guardian.shortcuts import get_users_with_perms
from haystack.query import SearchQuerySet

from course_discovery.apps.core.mixins import ModelPermissionsMixin
from course_discovery.apps.course_metadata.models import Course, CourseRun, Program


class Catalog(ModelPermissionsMixin, TimeStampedModel):
    VIEW_PERMISSION = 'view_catalog'
    name = models.CharField(max_length=255, null=False, blank=False, help_text=_('Catalog name'))
    query = models.TextField(null=False, blank=False, help_text=_('Query to retrieve Course Run catalog contents'))
    program_query = models.TextField(
        null=False,
        blank=True,
        help_text=_('Query to retrieve Program catalog contents'),
        default=''
    )
    include_archived = models.BooleanField(default=False, help_text=_('Include archived courses'))

    def __str__(self):
        return f'Catalog #{self.id}: {self.name}'

    def _get_query_results(self):
        """
        Returns the results of this Catalog's query.

        Returns:
            SearchQuerySet
        """
        return SearchQuerySet().models(Course).raw_search(self.query)

    def courses(self):
        """ Returns the list of courses contained within this catalog.

        Returns:
            QuerySet
        """
        return Course.search(self.query)

    def programs(self):
        """ Returns the list of Programs contained within this catalog.

        Returns:
            QuerySet
        """
        return Program.search(self.program_query)

    @property
    def courses_count(self):
        return self._get_query_results().count()

    def contains(self, course_ids):
        """ Determines if the given courses are contained in this catalog.

        Arguments:
            course_ids (str[]): List of course IDs

        Returns:
            dict: Mapping of course IDs to booleans indicating if course is
                  contained in this catalog.
        """
        contains = {course_id: False for course_id in course_ids}
        results = self._get_query_results().filter(key__in=course_ids)
        for result in results:
            contains[result.get_stored_fields()['key']] = True

        return contains

    def contains_course_runs(self, course_run_ids):
        """
        Determines if the given course runs are contained in this catalog.

        Arguments:
            course_run_ids (str[]): List of course run IDs

        Returns:
            dict: Mapping of course IDs to booleans indicating if course run is
                  contained in this catalog.
        """
        contains = {course_run_id: False for course_run_id in course_run_ids}
        course_runs = CourseRun.search(self.query).filter(key__in=course_run_ids).values_list('key', flat=True)
        contains.update({course_run_id: course_run_id in course_runs for course_run_id in course_run_ids})

        return contains

    @property
    def viewers(self):
        """ Returns a QuerySet of users who have been granted explicit access to view this Catalog.

        Returns:
            QuerySet
        """
        # NOTE (CCB): This method actually returns any individual User with *any* permission on the object. It is
        # safe to assume that those who can create/modify the model can also view it. If that assumption changes,
        # change this code!
        return get_users_with_perms(self, with_superusers=False, with_group_users=False)

    @viewers.setter
    def viewers(self, value):
        """ Sets the viewers of this model.

        This method utilizes Django permissions to set access. Existing user-specific access permissions will be
        overwritten. Group permissions will not be affected.

        Args:
            value (Iterable): Collection of `User` objects.

        Raises:
            TypeError: The given value is not iterable, or is a string.

        Returns:
            None
        """
        if isinstance(value, str) or not isinstance(value, Iterable):
            raise TypeError('Viewers must be a non-string iterable containing User objects.')

        new = set(value)
        existing = set(self.viewers)

        # Remove users who no longer have access
        to_be_removed = existing - new

        for user in to_be_removed:
            user.del_obj_perm(self.VIEW_PERMISSION, self)

        # Add new users
        new = new - existing

        for user in new:
            user.add_obj_perm(self.VIEW_PERMISSION, self)

    class Meta(TimeStampedModel.Meta):
        abstract = False
        permissions = (
            ('view_catalog', 'Can view catalog'),
        )
        # The view permission was added in 2.1, as result two view permissions tries to insert into db and triggers
        # integrity error. Customize the default permission list and removed view from there
        default_permissions = ('add', 'change', 'delete',)
