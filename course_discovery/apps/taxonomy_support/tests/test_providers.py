"""
Validate taxonomy integration.

This file validates the following
    1. Make sure the provider specified by `TAXONOMY_COURSE_METADATA_PROVIDER`, `TAXONOMY_PROGRAM_METADATA_PROVIDER`
       and `TAXONOMY_XBLOCK_METADATA_PROVIDER` implements all the abstract methods
    2. Make sure the signature of all the methods match with the interfaces of the abstract class
    3. Make sure the data returned and the structure of the data matches with the definitions inside the interface.

You will notice that none of the above assertions are directly happening in this file, the reason of this is that
these assertions and the related code is provided by the `CourseMetadataProviderValidator` from taxonomy. This file is
only responsible for populating test data, instantiating the validator with correct argument and calling the `validate`
method.

`validate` method will raise `AssertError` if any of the assertions do not pass.

Note: Course Metadata validator will use the provider pointed by the `TAXONOMY_COURSE_METADATA_PROVIDER` django setting.
Note: Program Metadata validator will use the provider pointed by the `TAXONOMY_PROGRAM_METADATA_PROVIDER` django
setting.
Note: XBlock Metadata validator will use the provider pointed by the `TAXONOMY_XBLOCK_METADATA_PROVIDER` django setting.

Reason behind keeping the validator a part of taxonomy-connector is to keep the provider and its validation logic in the
same repository, so whenever a new dependency (e.g. a new method or a new field in the returned data) is added in the
provider its validator is also updated in the same pull request. This ensures that the provider implementation in
discovery and its interface in taxonomy are always in sync.
"""
from unittest import mock
from urllib.parse import urljoin

from django.conf import settings
from django.test import TestCase
from taxonomy.validators import (
    CourseMetadataProviderValidator, ProgramMetadataProviderValidator, XBlockMetadataProviderValidator
)

from course_discovery.apps.core.tests.factories import PartnerFactory
from course_discovery.apps.core.tests.mixins import LMSAPIClientMixin
from course_discovery.apps.course_metadata.tests.factories import CourseFactory, ProgramFactory


class TaxonomyIntegrationTests(TestCase, LMSAPIClientMixin):
    """
    Validate integration of taxonomy_support and metadata providers.
    """
    @mock.patch('course_discovery.apps.taxonomy_support.providers.fetch_and_transform_bootcamp_contentful_data',
                return_value={})
    def test_validate_course_metadata(self, _contentful_data):
        """
        Validate that there are no integration issues.
        """
        courses = CourseFactory.create_batch(3)
        course_metadata_validator = CourseMetadataProviderValidator(
            [str(course.uuid) for course in courses]
        )

        # Run all the validations, note that an assertion error will be raised if any of the validation fail.
        course_metadata_validator.validate()

    @mock.patch('course_discovery.apps.taxonomy_support.providers.fetch_and_transform_degree_contentful_data',
                return_value={})
    def test_validate_program_metadata(self, _contentful_data):
        """
        Validate that there are no integration issues.
        """
        programs = ProgramFactory.create_batch(3)
        program_metadata_validator = ProgramMetadataProviderValidator(
            [str(program.uuid) for program in programs]
        )

        # Run all the validations, note that an assertion error will be raised if any of the validation fail.
        program_metadata_validator.validate()

    def test_validate_xblock_metadata(self):
        """
        Validate that there are no integration issues in xblock provider.
        """
        self.mock_access_token()
        partner = PartnerFactory.create(id=settings.DEFAULT_PARTNER_ID, lms_url='http://127.0.0.1:8000')
        block_ids = [
            'block-v1:edX+DemoX+Demo_Course+type@video+block@0b9e39477cf34507a7a48f74be381fdd',
            'block-v1:edX+DemoX+Demo_Course+type@vertical+block@vertical_0270f6de40fc',
        ]
        resource = settings.LMS_API_URLS['blocks']
        for block_id in block_ids:
            block_resource_url = urljoin(partner.lms_url, resource + block_id)
            block_metadata_url = urljoin(partner.lms_url, 'api/courses/v1/block_metadata/')
            self.mock_blocks_data_request(block_resource_url)
            self.mock_block_metadata_request(block_metadata_url)
        xblock_metadata_validator = XBlockMetadataProviderValidator(block_ids)

        # Run all the validations, note that an assertion error will be raised if any of the validation fail.
        xblock_metadata_validator.validate()
