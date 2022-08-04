"""
Course metadata provider for taxonomy app.

This file contains the implementation of the provider required by taxonomy app,
interface of this provider is provided by the taxonomy app at
https://github.com/edx/taxonomy-connector/blob/master/taxonomy/providers/course_metadata.py

Provider must implement all the methods with signature conforming to the interface provided, return type as well as
the structure of the data returned must match with the definitions inside the interface. The provider is exposed via
`TAXONOMY_COURSE_METADATA_PROVIDER` setting, taxonomy-connector will import and instantiate the class pointed by this
settings.

For a more detailed explanation of the implementation and thinking behind this provider can be found at
https://openedx.atlassian.net/wiki/spaces/SOL/pages/1814922129/Platform+Agnostic+Implementation+of+Taxonomy+Application
"""
from edx_django_utils.db import chunked_queryset
from taxonomy.providers import CourseMetadataProvider, ProgramProvider

from course_discovery.apps.course_metadata.models import Course, Program


class DiscoveryCourseMetadataProvider(CourseMetadataProvider):
    """
    Discovery course metadata provider.
    """

    @staticmethod
    def get_courses(course_ids):  # lint-amnesty, pylint: disable=arguments-differ
        """
        Get list of courses matching the given course UUIDs and return then in the form of a dict.
        """
        courses = Course.everything.filter(uuid__in=course_ids).distinct()
        return [{
            'uuid': course.uuid,
            'key': course.key,
            'title': course.title,
            'short_description': course.short_description,
            'full_description': course.full_description,
        } for course in courses]

    @staticmethod
    def get_all_courses():  # lint-amnesty, pylint: disable=arguments-differ
        """
        Get iterator for all the courses (excluding drafts).
        """
        all_courses = Course.objects.all()
        for chunked_courses in chunked_queryset(all_courses):
            for course in chunked_courses:
                yield {
                    'uuid': course.uuid,
                    'key': course.key,
                    'title': course.title,
                    'short_description': course.short_description,
                    'full_description': course.full_description,
                }


class DiscoveryProgramProvider(ProgramProvider):
    """
    Discovery Program provider.
    """

    @staticmethod
    def get_program(program_ids):
        """
        Get list of programs matching the given program UUIDs and return them in the form of a dict.
        """
        programs = Program.objects.filter(uuid__in=program_ids).distinct()
        return [{
            'uuid': program.uuid,
            'overview': program.overview,
        } for program in programs]

    @staticmethod
    def get_all_programs():  # lint-amnesty, pylint: disable=arguments-differ
        """
        Get iterator for all the programs (excluding drafts).
        """
        all_programs = Program.objects.all()
        for chunked_programs in chunked_queryset(all_programs):
            for program in chunked_programs:
                yield {
                    'uuid': program.uuid,
                    'overview': program.overview,
                }
