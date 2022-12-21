"""
Course metadata provider for taxonomy app.

This file contains the implementation of the provider required by taxonomy app,
interface of this provider is provided by the taxonomy app at
https://github.com/openedx/taxonomy-connector/blob/master/taxonomy/providers/course_metadata.py

Provider must implement all the methods with signature conforming to the interface provided, return type as well as
the structure of the data returned must match with the definitions inside the interface. The provider is exposed via
`TAXONOMY_COURSE_METADATA_PROVIDER` setting, taxonomy-connector will import and instantiate the class pointed by this
settings.

For a more detailed explanation of the implementation and thinking behind this provider can be found at
https://openedx.atlassian.net/wiki/spaces/SOL/pages/1814922129/Platform+Agnostic+Implementation+of+Taxonomy+Application
"""
from edx_django_utils.db import chunked_queryset
from taxonomy.providers import CourseMetadataProvider, ProgramMetadataProvider

from course_discovery.apps.course_metadata.contentful_utils import (
    fetch_and_transform_bootcamp_contentful_data, get_aggregated_data_from_contentful_data
)
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
        contentful_data = fetch_and_transform_bootcamp_contentful_data()
        return [{
            'uuid': course.uuid,
            'key': course.key,
            'title': course.title,
            'short_description': course.short_description,
            'full_description': (
                get_aggregated_data_from_contentful_data(contentful_data, course.uuid) or course.full_description
            ),
        } for course in courses]

    @staticmethod
    def get_all_courses():  # lint-amnesty, pylint: disable=arguments-differ
        """
        Get iterator for all the courses (excluding drafts).
        """
        all_courses = Course.objects.all()
        contentful_data = fetch_and_transform_bootcamp_contentful_data()
        for chunked_courses in chunked_queryset(all_courses):
            for course in chunked_courses:
                yield {
                    'uuid': course.uuid,
                    'key': course.key,
                    'title': course.title,
                    'short_description': course.short_description,
                    'full_description': (
                        get_aggregated_data_from_contentful_data(contentful_data, course.uuid) or
                        course.full_description
                    ),
                }


class DiscoveryProgramMetadataProvider(ProgramMetadataProvider):
    """
    Discovery program provider.
    """

    @staticmethod
    def get_programs(program_ids):  # lint-amnesty, pylint: disable=arguments-differ
        """
        Get list of programs matching the given program UUIDs and return then in the form of a dict.
        """
        programs = Program.objects.filter(uuid__in=program_ids).distinct()
        # Todo: use transform_degree_contentful_data method to get data from contentful
        contentful_data = {}
        return [{
            'uuid': program.uuid,
            'title': program.title,
            'subtitle': program.subtitle,
            'overview': get_aggregated_data_from_contentful_data(contentful_data, program.uuid) or program.overview,
        } for program in programs]

    @staticmethod
    def get_all_programs():  # lint-amnesty, pylint: disable=arguments-differ
        """
        Get iterator for all the programs.
        """
        all_programs = Program.objects.all()
        # Todo: use transform_degree_contentful_data method to get data from contentful
        contentful_data = {}
        for chunked_programs in chunked_queryset(all_programs):
            for program in chunked_programs:
                yield {
                    'uuid': program.uuid,
                    'title': program.title,
                    'subtitle': program.subtitle,
                    'overview': (
                        get_aggregated_data_from_contentful_data(contentful_data, program.uuid) or program.overview
                    ),
                }
