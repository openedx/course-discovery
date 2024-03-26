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
from django.conf import settings
from django.utils.translation import gettext_lazy as _
from edx_django_utils.db import chunked_queryset
from taxonomy.providers import (
    CourseMetadataProvider, CourseRunContent, CourseRunMetadataProvider, ProgramMetadataProvider, XBlockContent,
    XBlockMetadataProvider
)

from course_discovery.apps.core.api_client.lms import LMSAPIClient
from course_discovery.apps.core.models import Partner
from course_discovery.apps.course_metadata.choices import CourseRunStatus
from course_discovery.apps.course_metadata.contentful_utils import (
    aggregate_contentful_data, fetch_and_transform_bootcamp_contentful_data, fetch_and_transform_degree_contentful_data
)
from course_discovery.apps.course_metadata.models import Course, CourseRun, Organization, Program


class DiscoveryCourseMetadataProvider(CourseMetadataProvider):
    """
    Discovery course metadata provider.
    """

    @staticmethod
    def get_courses(course_ids):  # lint-amnesty, pylint: disable=arguments-differ
        """
        Get list of courses matching the given course UUIDs and return them in the form of a dict.
        """
        courses = Course.everything.filter(uuid__in=course_ids).distinct()
        contentful_data = fetch_and_transform_bootcamp_contentful_data()
        return [{
            'uuid': course.uuid,
            'key': course.key,
            'title': course.title,
            'short_description': course.short_description,
            'full_description': (
                aggregate_contentful_data(contentful_data, str(course.uuid)) or course.full_description
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
                        aggregate_contentful_data(contentful_data, str(course.uuid)) or
                        course.full_description
                    ),
                }

    def get_course_key(self, course_run_key):
        """
        Get course key for the given `course_run_key`.

        Arguments:
            course_run_key(str): course run key

        Returns:
            str: course key if course run exists, None otherwise
        """
        return CourseRun.objects.filter(key=course_run_key).values_list('course__key', flat=True).first()

    def is_valid_course(self, course_key):
        """
        Validate that a course with given `course_key` exists.

        Arguments:
          course_key(str): course key

        Returns:
          bool: True if course is valid, False otherwise
        """
        return Course.objects.filter(key=course_key).exists()

    def is_valid_organization(self, organization_key):
        """
        Validate that an organization with given `organization_key` exists.

        Arguments:
          organization_key(str): organization key

        Returns:
          bool: True if organization is valid, False otherwise
        """
        return Organization.objects.filter(key=organization_key).exists()


class DiscoveryCourseRunMetadataProvider(CourseRunMetadataProvider):
    """
    Discovery course run metadata provider.
    """

    @staticmethod
    def get_course_runs(course_run_keys):  # lint-amnesty, pylint: disable=arguments-differ
        """
        Get list of course runs matching the given course run keys and return them in the form of CourseRunContent.
        """
        course_runs = CourseRun.objects.filter(key__in=course_run_keys).distinct()
        return [
            CourseRunContent(course_run_key=course_run.key, course_key=course_run.course.key)
            for course_run in course_runs
        ]

    @staticmethod
    def get_all_published_course_runs():  # lint-amnesty, pylint: disable=arguments-differ
        """
        Get iterator for all published course runs.
        """
        all_courses = Course.objects.all()
        for chunked_courses in chunked_queryset(all_courses):
            for course in chunked_courses:
                course_runs = course.course_runs.filter(status=CourseRunStatus.Published).all()
                for chunked_course_runs in chunked_queryset(course_runs):
                    for course_run in chunked_course_runs:
                        yield CourseRunContent(course_run_key=course_run.key, course_key=course.key)


class DiscoveryProgramMetadataProvider(ProgramMetadataProvider):
    """
    Discovery program provider.
    """

    @staticmethod
    def get_programs(program_ids):  # lint-amnesty, pylint: disable=arguments-differ
        """
        Get list of programs matching the given program UUIDs and return them in the form of a dict.
        """
        programs = Program.objects.filter(uuid__in=program_ids).distinct()
        contentful_data = fetch_and_transform_degree_contentful_data()
        return [{
            'uuid': program.uuid,
            'title': program.title,
            'subtitle': program.subtitle,
            'overview': (
                aggregate_contentful_data(contentful_data, str(program.uuid)) or
                program.overview
            ),
        } for program in programs]

    @staticmethod
    def get_all_programs():  # lint-amnesty, pylint: disable=arguments-differ
        """
        Get iterator for all the programs.
        """
        all_programs = Program.objects.all()
        contentful_data = fetch_and_transform_degree_contentful_data()
        for chunked_programs in chunked_queryset(all_programs):
            for program in chunked_programs:
                yield {
                    'uuid': program.uuid,
                    'title': program.title,
                    'subtitle': program.subtitle,
                    'overview': (
                        aggregate_contentful_data(contentful_data, str(program.uuid)) or
                        program.overview
                    ),
                }


class DiscoveryXBlockMetadataProvider(XBlockMetadataProvider):
    """
    Discovery xblock provider.
    """

    def __init__(self):
        """
        Get lms client with default partner object.
        """
        if settings.DEFAULT_PARTNER_ID:
            partner = Partner.objects.filter(id=settings.DEFAULT_PARTNER_ID).first()
        else:
            partner = Partner.objects.first()
        if partner is None:
            raise KeyError(_('No partner object found!'))
        self.client = LMSAPIClient(partner)

    def _get_block_content(self, block_id: str, block_type: str) -> list:
        """
        Fetches block metadata i.e. `index_dictionary` using lms api and
        returns content values as unique list.
        """
        block_metadata = self.client.get_blocks_metadata(block_id) or {}
        content = block_metadata.get('index_dictionary', {}).get('content', {})
        content_list = []
        for key, content_text in content.items():
            # Ignore non english transcripts till we figure out a way to translate them.
            # https://github.com/openedx/taxonomy-connector/blob/master/taxonomy/utils.py#L291-L292
            if block_type == 'video' and key.startswith('transcript_') and key != 'transcript_en':
                continue
            content_text = str(content_text).strip() if content_text else None
            if content_text:
                content_list.append(content_text)
        return content_list

    def _combine_text_data(self, cur_block, all_blocks):
        """
        Recursively combines content values in all children blocks.
        """
        block_id = cur_block.get('id')
        block_type = cur_block.get('type')
        content_list = []
        if block_id:
            content_list = self._get_block_content(block_id, block_type)
        for child in cur_block.get('children', []):
            child_block = all_blocks.get(child)
            if child_block:
                content_list.extend(self._combine_text_data(child_block, all_blocks))
        # return ordered unique list of content.
        return list(dict.fromkeys(content_list))

    def get_xblocks(self, xblock_ids):
        """
        Get list of xblocks matching the given xblock UUIDs and return them in
        the form of XBlockContent.
        """

        blocks_data = set()
        for block_id in xblock_ids:
            all_blocks = self.client.get_blocks_data(block_id) or {}
            for block in all_blocks.values():
                if block['type'] in settings.TAXONOMY_XBLOCK_SUPPORTED_TYPES:
                    content = '\n'.join(self._combine_text_data(block, all_blocks))
                    blocks_data.add(XBlockContent(
                        key=block.get('id'),
                        content_type=block.get('type'),
                        content=content,
                    ))
        return list(blocks_data)

    def get_all_xblocks_in_course(self, course_id: str):
        """
        Get iterator for all unit/video xblocks in course
        """
        blocks = self.client.get_course_blocks_data(course_id) or {}

        for block in blocks.values():
            if block['type'] in settings.TAXONOMY_XBLOCK_SUPPORTED_TYPES:
                content = '\n'.join(self._combine_text_data(block, blocks))
                yield XBlockContent(
                    key=block.get('id'),
                    content_type=block.get('type'),
                    content=content,
                )
