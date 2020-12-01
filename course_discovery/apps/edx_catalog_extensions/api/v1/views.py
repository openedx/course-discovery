import logging
from collections import defaultdict
from uuid import UUID

from django.contrib.sites.models import Site
from django.core.serializers import json
from django.http.response import HttpResponse
from rest_framework.permissions import IsAdminUser
from rest_framework.views import APIView

from course_discovery.apps.api.v1.views.search import AggregateSearchViewSet
from course_discovery.apps.core.models import Partner, User
from course_discovery.apps.core.utils import use_read_replica_if_available
from course_discovery.apps.course_metadata.models import (
    CourseRun, Curriculum, CurriculumCourseMembership, CurriculumCourseRunExclusion, CurriculumProgramMembership,
    Program
)
from course_discovery.apps.edx_catalog_extensions.api.serializers import DistinctCountsAggregateFacetSearchSerializer
from course_discovery.apps.edx_haystack_extensions.distinct_counts.query import DistinctCountsSearchQuerySet

logger = logging.getLogger(__name__)


class DistinctCountsAggregateSearchViewSet(AggregateSearchViewSet):
    """ Provides a facets action that can include distinct hit and facet counts in the response."""

    # Custom serializer that includes distinct hit and facet counts.
    facet_serializer_class = DistinctCountsAggregateFacetSearchSerializer

    def get_queryset(self, *args, **kwargs):  # pylint: disable=arguments-differ
        """ Return the base Queryset to use to build up the search query."""
        queryset = super().get_queryset(*args, **kwargs)
        return DistinctCountsSearchQuerySet.from_queryset(queryset).with_distinct_counts('aggregation_key')


class ProgramFixtureView(APIView):
    """
    Returns a JSON fixture of program data suitable for use with Django's
    loaddata command.

    Query parameters:
        * programs: comma-separated list of program UUIDs

    Allowed methods:
        * GET

    Response codes:
        * 200: Program fixture successfully fetched.
        * 403: User not staff.
        * 404: One or more program UUIDs invalid.
        * 422: Too many programs requested.

    Example:
        Request:
            GET /extensions/api/v1/program-fixture?programs=<uuid1>,<uuid2>
        Response: 200 OK
            <list of JSON fixture objects>
    """
    permission_classes = (IsAdminUser,)
    QUERY_PARAM = 'programs'
    HELP_STRING = 'Must provide comma-separated list of valid UUIDs in "program" query parameter.'
    MAX_REQUESTED_PROGRAMS = 10

    def get(self, request):
        uuids_string = self.request.GET.get(self.QUERY_PARAM)
        if not uuids_string:
            return HttpResponse(self.HELP_STRING, status=404)
        uuids_split = uuids_string.split(',')
        try:
            uuids = {UUID(uuid_str) for uuid_str in uuids_split}
        except ValueError:
            return HttpResponse(self.HELP_STRING, status=404)
        if len(uuids) > self.MAX_REQUESTED_PROGRAMS:
            return HttpResponse(
                f'Too many programs requested, only {self.MAX_REQUESTED_PROGRAMS} allowed.',
                status=422,
            )
        programs = use_read_replica_if_available(
            Program.objects.filter(uuid__in=list(uuids))
        )
        loaded_uuids = {program.uuid for program in programs}
        bad_uuids = uuids - loaded_uuids
        if bad_uuids:
            return HttpResponse(
                "Could not load programs from UUIDs: [{}]".format(
                    ",".join(str(uuid) for uuid in bad_uuids)
                ),
                status=404,
            )
        objects = load_program_fixture(programs)
        json_text = json.Serializer().serialize(objects)
        return HttpResponse(json_text, content_type='text/json')


def load_program_fixture(programs):
    """
    Given a list of of programs, load:
    * Each program
    * All associated curricula
    * All associated curriciulum program/course memberships and course-run
      exclusions
    * All models that the above reference, either by foreign key or
      or explicit many-to-many relationship.

    Arguments:
        programs (iterable[Program])

    Returns: list[Model]
    """
    curricula_pks = use_read_replica_if_available(
        Curriculum.objects.filter(
            program__in=programs
        ).values_list('pk', flat=True)
    )
    course_memberships = use_read_replica_if_available(
        CurriculumCourseMembership.objects.filter(
            curriculum__in=curricula_pks
        ).values_list('pk', 'course_id')
    )
    course_membership_pks = [pk for pk, _ in course_memberships]
    course_pks = [course_pk for _, course_pk in course_memberships]
    course_run_pks = use_read_replica_if_available(
        CourseRun.objects.filter(
            course__in=course_pks
        ).values_list('pk', flat=True)
    )
    program_membership_pks = use_read_replica_if_available(
        CurriculumProgramMembership.objects.filter(
            curriculum__in=curricula_pks
        ).values_list('pk', flat=True)
    )
    exclusion_pks = use_read_replica_if_available(
        CurriculumCourseRunExclusion.objects.filter(
            course_membership__in=course_membership_pks
        ).values_list('pk', flat=True)
    )
    pks_to_load = {
        Program: {program.pk for program in programs},
        Curriculum: set(curricula_pks),
        CurriculumCourseMembership: set(course_membership_pks),
        CurriculumProgramMembership: set(program_membership_pks),
        CourseRun: set(course_run_pks),
        CurriculumCourseRunExclusion: set(exclusion_pks),
    }
    excluded_models = {Site, Partner, User}
    return load_related(pks_to_load, excluded_models)


def load_related(pks_to_load, excluded_models):
    """
    Given a set of root models and primary keys, load all objects
    related either by foreign key or explicit many-to-many relationship.

    Arguments:
        pks_to_load (dict[type, set[int]]):
            Mapping from root model classes to primary keys of
                the instances of them to load first.
        excluded_models (frozenset[type]):
            Model classes that we are not to load or traverse.

    Returns: list[Model]
    """

    # Mapping from each model to a PK->instance dict.
    # Is used as input and output for this function; is mutated.
    # A PK that maps to a model instance is part of the result set.
    # A PK that maps to None means that the PK is referenced by some
    #     model instance, but we haven't loaded it yet.
    # The result set is complete when all the PKs map to loaded instances.
    results_by_model = defaultdict(dict, {
        model: {pk: None for pk in pks}
        for model, pks in pks_to_load.items()
    })

    while True:

        # Choose a model that has instances that we still need to load.
        model = None
        pks_to_load = None
        for model, results in results_by_model.items():
            pks_to_load = {
                pk for pk, instance in results.items()
                if not instance
            }
            if pks_to_load:
                break
        else:
            # All models fully loaded; return results flattened into a list.
            return [
                instance
                for results in results_by_model.values()
                for instance in results.values()
            ]

        # Load new instances and add them to `results_by_model`.
        # Use the *base* Django object manager.
        # Otherwise, models that redefine `objects` may leave out objects
        # that we want.
        # For example, subclasses of DraftModelMixin redefine `objects`
        # to exclude drafts, which would break this function.
        all_objects = model._base_manager  # pylint: disable=protected-access
        objects = use_read_replica_if_available(
            all_objects.filter(pk__in=pks_to_load)
        )
        objects_by_pk = {obj.pk: obj for obj in objects}
        pks_failed_to_load = pks_to_load - set(objects_by_pk.keys())
        if pks_failed_to_load:
            raise Exception(
                "Failed to load some objects required for fixture: " +
                "Model = " + model._meta.label + ", "
                "PKs of failed objects = " + str(pks_failed_to_load)
            )
        results_by_model[model].update(objects_by_pk)

        # For all relational fields on the model, update
        # `results_by_model` with holes for referenced instances that we
        # have not yet loaded.
        for field in model._meta.fields + model._meta.many_to_many:
            rel_model = field.related_model
            if not rel_model:
                continue
            if rel_model in excluded_models:
                continue
            rel_pks_name = f"{field.name}__pk"
            rel_pks = objects.values_list(rel_pks_name, flat=True)
            results_by_model[rel_model].update({
                pk: results_by_model[rel_model].get(pk)
                for pk in rel_pks if pk
            })
