"""
Unit tests for Degree CSV Data loader.
"""
from tempfile import NamedTemporaryFile
from unittest import mock

import ddt
import responses
from django.test import override_settings
from testfixtures import LogCapture

from course_discovery.apps.api.v1.tests.test_views.mixins import APITestCase, OAuth2Mixin
from course_discovery.apps.core.tests.factories import USER_PASSWORD, UserFactory
from course_discovery.apps.course_metadata.choices import ProgramStatus
from course_discovery.apps.course_metadata.data_loaders.degrees_loader import DegreeCSVDataLoader
from course_discovery.apps.course_metadata.data_loaders.tests import mock_data
from course_discovery.apps.course_metadata.data_loaders.tests.mixins import DegreeCSVLoaderMixin
from course_discovery.apps.course_metadata.models import Curriculum, Degree, Program
from course_discovery.apps.course_metadata.tests.factories import DegreeAdditionalMetadataFactory, DegreeFactory

LOGGER_PATH = 'course_discovery.apps.course_metadata.data_loaders.degrees_loader'


@ddt.ddt
@mock.patch(
    'course_discovery.apps.course_metadata.data_loaders.configured_jwt_decode_handler',
    return_value={'preferred_username': 'test_username'}
)
class TestDegreeCSVDataLoader(DegreeCSVLoaderMixin, OAuth2Mixin, APITestCase):
    """
    Test Suite for DegreeCSVLoader.
    """

    def setUp(self) -> None:
        super().setUp()
        self.mock_access_token()
        self.user = UserFactory.create(username="test_user", password=USER_PASSWORD, is_staff=True)
        self.client.login(username=self.user.username, password=USER_PASSWORD)

    def _assert_default_logs(self, log_capture):
        """
        Assert the initiation and completion logs are present in the logger.
        """
        log_capture.check_present(
            (
                LOGGER_PATH,
                'INFO',
                'Initiating Degree CSV data loader flow.'
            ),
            (
                LOGGER_PATH,
                'INFO',
                'Degree CSV loader ingest pipeline has completed.'
            )

        )

    @override_settings(DEGREE_VARIANTS_FIELD_MAP={'text-source': ['courses']})
    @ddt.data('identifier', 'card_image_url', 'title', 'paid_landing_page_url', 'organic_url', 'courses')
    def test_validation_failure(self, missing_key, jwt_decode_patch):  # pylint: disable=unused-argument
        """
        Verify that data validation fails given an invalid data.
        """
        self._setup_prerequisites(self.partner)
        INVALID_DEGREE_CSV_DICT = {
            **mock_data.VALID_DEGREE_CSV_DICT,
            missing_key: ''
        }
        with NamedTemporaryFile() as csv:
            csv = self._write_csv(csv, [INVALID_DEGREE_CSV_DICT])
            with LogCapture(LOGGER_PATH) as log_capture:
                loader = DegreeCSVDataLoader(self.partner, csv_path=csv.name, product_source=self.product_source.slug)
                loader.ingest()
                self._assert_default_logs(log_capture)
                log_capture.check_present(
                    (
                        LOGGER_PATH,
                        'ERROR',
                        '[MISSING_REQUIRED_DATA] Degree {degree_slug} is missing the required data for '
                        'ingestion. The missing data elements are "{missing_data}"'.format(
                            degree_slug=self.DEGREE_SLUG,
                            missing_data=missing_key
                        )
                    )
                )
                assert Degree.objects.count() == 0

    def test_missing_organization(self, jwt_decode_patch):  # pylint: disable=unused-argument
        """
        Verify that no degree is created for a missing organization in the database.
        """
        with NamedTemporaryFile() as csv:
            csv = self._write_csv(csv, [mock_data.INVALID_DEGREE_ORGANIZATION_DATA])
            with LogCapture(LOGGER_PATH) as log_capture:
                loader = DegreeCSVDataLoader(self.partner, csv_path=csv.name, product_source=self.product_source.slug)
                loader.ingest()
                self._assert_default_logs(log_capture)
                log_capture.check_present(
                    (
                        LOGGER_PATH,
                        'ERROR',
                        '[MISSING_ORGANIZATION] Unable to locate partner organization with key invalid-organization '
                        'for the degree {degree_slug}.'.format(degree_slug=self.DEGREE_SLUG)
                    ),
                )
                assert Degree.objects.count() == 0

    def test_invalid_program_type(self, jwt_decode_patch):  # pylint: disable=unused-argument
        """
        Verify that no degree is created for an invalid program type.
        """
        self._setup_organization(self.partner)
        with NamedTemporaryFile() as csv:
            csv = self._write_csv(csv, [mock_data.INVALID_PROGRAM_TYPE_DATA])
            with LogCapture(LOGGER_PATH) as log_capture:
                loader = DegreeCSVDataLoader(self.partner, csv_path=csv.name, product_source=self.product_source.slug)
                loader.ingest()
                self._assert_default_logs(log_capture)
                log_capture.check_present(
                    (
                        LOGGER_PATH,
                        'ERROR',
                        '[MISSING_PROGRAM_TYPE] Unable to find the program type "invalid-program-type" '
                        'for the degree {degree_slug}'.format(degree_slug=self.DEGREE_SLUG)
                    )
                )
                assert Degree.objects.count() == 0

    @responses.activate
    def test_single_valid_row(self, jwt_decode_patch):  # pylint: disable=unused-argument
        """
        Verify that for a single row of valid data, degree is created.
        """
        self._setup_prerequisites(self.partner)
        _, image_content = self.mock_image_response()

        with NamedTemporaryFile() as csv:
            csv = self._write_csv(csv, [mock_data.VALID_DEGREE_CSV_DICT])

            with LogCapture(LOGGER_PATH) as log_capture:
                loader = DegreeCSVDataLoader(self.partner, csv_path=csv.name, product_source=self.product_source.slug)
                loader.ingest()

                self._assert_default_logs(log_capture)
                log_capture.check_present(
                    (
                        LOGGER_PATH,
                        'INFO',
                        'Degree with external identifier {} is not located in the database. Creating new degree.'.format(self.EXTERNAL_IDENTIFIER)  # pylint: disable=line-too-long
                    )
                )

                assert Degree.objects.count() == 1
                assert Program.objects.count() == 1
                assert Curriculum.objects.count() == 1

                degree = Degree.objects.get(marketing_slug=self.DEGREE_SLUG, partner=self.partner)
                program = Program.objects.get(degree=degree, partner=self.partner)
                curriculam = Curriculum.objects.get(program=program)

                assert degree.card_image.read() == image_content
                assert degree.specializations.count() == 2
                assert curriculam.marketing_text == self.marketing_text
                self._assert_degree_data(degree, self.BASE_EXPECTED_DEGREE_DATA)
                assert loader.get_ingestion_stats() == {
                    'total_products_count': 1,
                    'success_count': 1,
                    'failure_count': 0,
                    'updated_products_count': 0,
                    'created_products_count': 1,
                    'created_products': [{'uuid': str(degree.uuid)}],
                    'errors': loader.error_logs
                }
                assert degree.product_source == self.product_source

    def test_ingest_flow_for_preexisting_degree(self, jwt_decode_patch):  # pylint: disable=unused-argument
        """
        Verify that the loader updates the existing degree in database.
        """

        self._setup_prerequisites(self.partner)
        _, image_content = self.mock_image_response()

        degree = DegreeFactory(
            marketing_slug=self.DEGREE_SLUG, partner=self.partner,
            type=self.program_type, product_source=self.product_source
        )
        _ = DegreeAdditionalMetadataFactory(degree=degree, external_identifier='123456')

        with NamedTemporaryFile() as csv:
            csv = self._write_csv(csv, [mock_data.VALID_DEGREE_CSV_DICT])

            with LogCapture(LOGGER_PATH) as log_capture:
                loader = DegreeCSVDataLoader(self.partner, csv_path=csv.name, product_source=self.product_source.slug)
                loader.ingest()

                self._assert_default_logs(log_capture)
                log_capture.check_present(
                    (
                        LOGGER_PATH,
                        'INFO',
                        'Degree with external identifier {} is located in the database. Updating existing degree.'.format(self.EXTERNAL_IDENTIFIER)  # pylint: disable=line-too-long
                    )
                )
                assert Degree.objects.count() == 1
                assert Program.objects.count() == 1
                assert Curriculum.objects.count() == 1

                degree = Degree.objects.get(marketing_slug=self.DEGREE_SLUG, partner=self.partner)
                program = Program.objects.get(degree=degree, partner=self.partner)
                curriculam = Curriculum.objects.get(program=program)

                assert degree.specializations.count() == 2
                assert curriculam.marketing_text == self.marketing_text
                assert degree.card_image.read() == image_content
                self._assert_degree_data(degree, self.BASE_EXPECTED_DEGREE_DATA)
                assert loader.get_ingestion_stats() == {
                    'total_products_count': 1,
                    'success_count': 1,
                    'failure_count': 0,
                    'updated_products_count': 1,
                    'created_products_count': 0,
                    'created_products': [],
                    'errors': loader.error_logs
                }
                assert degree.product_source == self.product_source

    def test_ingest_flow_for_minimal_degree_data(self, jwt_decode_patch):  # pylint: disable=unused-argument
        """
        Verify that the loader runs as expected for minimal set of data.
        """
        self._setup_prerequisites(self.partner)
        _, image_content = self.mock_image_response()

        with NamedTemporaryFile() as csv:
            csv = self._write_csv(
                csv, [mock_data.VALID_DEGREE_CSV_DICT], self.MINIMAL_CSV_DATA_KEYS_ORDER
            )

            with LogCapture(LOGGER_PATH) as log_capture:
                loader = DegreeCSVDataLoader(self.partner, csv_path=csv.name, product_source=self.product_source.slug)
                loader.ingest()

                self._assert_default_logs(log_capture)
                log_capture.check_present(
                    (
                        LOGGER_PATH,
                        'INFO',
                        'Degree with external identifier {} is not located in the database. Creating new degree.'.format(self.EXTERNAL_IDENTIFIER)  # pylint: disable=line-too-long
                    )
                )

                assert Degree.objects.count() == 1
                assert Program.objects.count() == 1
                assert Curriculum.objects.count() == 1

                degree = Degree.objects.get(marketing_slug=self.DEGREE_SLUG, partner=self.partner)
                program = Program.objects.get(degree=degree, partner=self.partner)
                curriculam = Curriculum.objects.get(program=program)

                assert degree.card_image.read() == image_content
                assert program.organization_logo_override.read() == image_content
                assert degree.specializations.count() == 2
                assert curriculam.marketing_text == self.marketing_text

                assert degree.title == 'Test Degree'
                assert degree.overview == 'Test Degree Overview'
                assert degree.type == self.program_type
                assert degree.marketing_slug == 'test-degree'
                assert degree.additional_metadata.external_url == 'http://example.com/landing-page.html'
                assert degree.additional_metadata.external_identifier == '123456'
                assert degree.additional_metadata.organic_url == 'http://example.com/organic-page.html'
                assert degree.specializations.count() == 2
                assert degree.status == ProgramStatus.Unpublished
                assert degree.product_source == self.product_source

    @responses.activate
    def test_image_download_failure(self, jwt_decode_patch):  # pylint: disable=unused-argument
        """
        Verify that if the degree image download fails, the ingestion does not complete.
        """
        self._setup_prerequisites(self.partner)
        responses.add(
            responses.GET,
            'https://example.com/image.jpg',
            status=400,
            body='Image unavailable',
            content_type='image/jpeg',
        )

        with NamedTemporaryFile() as csv:
            csv = self._write_csv(csv, [mock_data.VALID_DEGREE_CSV_DICT])

            with LogCapture(LOGGER_PATH) as log_capture:
                loader = DegreeCSVDataLoader(self.partner, csv_path=csv.name, product_source=self.product_source.slug)
                loader.ingest()

                self._assert_default_logs(log_capture)
                log_capture.check_present(
                    (
                        LOGGER_PATH,
                        'INFO',
                        'Degree with external identifier {} is not located in the database. Creating new degree.'.format(self.EXTERNAL_IDENTIFIER)  # pylint: disable=line-too-long
                    )
                )

                # Creation call results in creating degree
                assert Degree.objects.count() == 1

                log_capture.check_present(
                    (
                        LOGGER_PATH,
                        'ERROR',
                        '[IMAGE_DOWNLOAD_FAILURE] The degree image download failed for the degree'
                        ' {degree_slug}.'.format(degree_slug=self.DEGREE_SLUG)
                    )
                )

    def test_invalid_product_source(self, _jwt_decode_patch):
        """
        Verify that no degree is created for an invalid product source
        """
        self._setup_organization(self.partner)
        with NamedTemporaryFile() as csv:
            csv = self._write_csv(csv, [mock_data.INVALID_PROGRAM_TYPE_DATA])
            with LogCapture(LOGGER_PATH) as log_capture:
                loader = DegreeCSVDataLoader(self.partner, csv_path=csv.name, product_source=self.product_source.slug)
                loader.ingest()
                self._assert_default_logs(log_capture)
                self.assertRaisesMessage(Exception, 'abc')
                assert Degree.objects.count() == 0

    def test_ofac_restricted_programs(self, _jwt_decode_patch):
        """
        Verify that degree is ofac restricted and active if program type exist in restricted types
        """
        self._setup_prerequisites(self.partner)
        self.product_source.ofac_restricted_program_types.add(self.program_type)
        with NamedTemporaryFile() as csv:
            csv = self._write_csv(csv, [mock_data.VALID_DEGREE_CSV_DICT])
            with LogCapture(LOGGER_PATH) as log_capture:
                loader = DegreeCSVDataLoader(self.partner, csv_path=csv.name, product_source=self.product_source.slug)
                loader.ingest()
                self._assert_default_logs(log_capture)
                degree = Degree.objects.first()
                assert degree.has_ofac_restrictions
                assert degree.ofac_comment == f"Program type {self.program_type.slug} is OFAC restricted " \
                                              f"for {self.product_source.name}"

    def test_slug_update_flow__for_existing_degree(self, jwt_decode_patch):  # pylint: disable=unused-argument
        """
        Verify that the loader updates the slugs for existing degree in database.
        """

        self._setup_prerequisites(self.partner)
        self.mock_image_response()

        degree = DegreeFactory(
            marketing_slug=self.DEGREE_SLUG, partner=self.partner,
            type=self.program_type, product_source=self.product_source
        )
        _ = DegreeAdditionalMetadataFactory(degree=degree, external_identifier='123456')
        updated_slug = 'test-degree-2'

        degree_data = mock_data.VALID_DEGREE_CSV_DICT.copy()
        degree_data['slug'] = updated_slug
        with NamedTemporaryFile() as csv:
            csv = self._write_csv(csv, [degree_data])

            loader = DegreeCSVDataLoader(self.partner, csv_path=csv.name, product_source=self.product_source.slug)
            loader.ingest()

            assert Degree.objects.count() == 1
            assert Program.objects.count() == 1
            assert Curriculum.objects.count() == 1
            assert Degree.objects.first().marketing_slug == updated_slug
