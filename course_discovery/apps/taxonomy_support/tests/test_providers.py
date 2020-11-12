"""
Validate taxonomy integration.

This file validates the following
    1. Make sure the provider specified by `TAXONOMY_COURSE_METADATA_PROVIDER` implements all the abstract methods
    2. Make sure the signature of all the methods match with the interfaces of the abstract class
    3. Make sure the data returned and the structure of the data matches with the definitions inside the interface.

You will notice that none of the above assertions are directly happening in this file, the reason of this is that
these assertions and the related code is provided by the `CourseMetadataProviderValidator` from taxonomy. This file is
only responsible for populating test data, instantiating the validator with correct argument and calling the `validate`
method.

`validate` method will raise `AssertError` if any of the assertions do not pass.

Note: Validator will use the provider pointed by the `TAXONOMY_COURSE_METADATA_PROVIDER` django setting.

Reason behind keeping the validator a part of taxonomy-connector is to keep the provider and its validation logic in the
same repository, so whenever a new dependency (e.g. a new method or a new field in the returned data) is added in the
provider its validator is also updated in the same pull request. This ensures that the provider implementation in
discovery and its interface in taxonomy are always in sync.
"""

from django.test import TestCase
from taxonomy.validators import CourseMetadataProviderValidator  # pylint: disable=no-name-in-module,import-error

from course_discovery.apps.course_metadata.tests.factories import CourseFactory


class TaxonomyIntegrationTests(TestCase):
    """
    Validate integration of taxonomy_support and metadata providers.
    """

    def test_validate(self):
        """
        Validate that there are no integration issues.
        """
        courses = CourseFactory.create_batch(3)
        course_metadata_validator = CourseMetadataProviderValidator(
            [str(course.uuid) for course in courses]
        )

        # Run all the validations, note that an assertion error will be raised if any of the validation fail.
        course_metadata_validator.validate()
