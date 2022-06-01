"""
Unit tests for Degree CSV Data loader.
"""
from tempfile import NamedTemporaryFile
from unittest import mock

import responses
from ddt import ddt
from testfixtures import LogCapture

from course_discovery.apps.api.v1.tests.test_views.mixins import APITestCase, OAuth2Mixin
from course_discovery.apps.core.tests.factories import USER_PASSWORD, UserFactory
from course_discovery.apps.course_metadata.data_loaders.degrees_loader import DegreeCSVDataLoader
from course_discovery.apps.course_metadata.data_loaders.tests import mock_data
from course_discovery.apps.course_metadata.data_loaders.tests.mixins import DegreeCSVLoaderMixin
from course_discovery.apps.course_metadata.models import Curriculum, Degree, Program
from course_discovery.apps.course_metadata.tests.factories import DegreeAdditionalMetadataFactory, DegreeFactory

LOGGER_PATH = 'course_discovery.apps.course_metadata.data_loaders.degrees_loader'


@ddt
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

    def test_missing_organization(self, jwt_decode_patch):  # pylint: disable=unused-argument
        """
        Verify that no degree is created for a missing organization in the database.
        """
        with NamedTemporaryFile() as csv:
            csv = self._write_csv(csv, [mock_data.INVALID_DEGREE_ORGANIZATION_DATA])
            with LogCapture(LOGGER_PATH) as log_capture:
                loader = DegreeCSVDataLoader(self.partner, csv_path=csv.name)
                loader.ingest()
                self._assert_default_logs(log_capture)
                log_capture.check_present(
                    (
                        LOGGER_PATH,
                        'ERROR',
                        'Organization invalid-organization does not exist. Skipping CSV '
                        'loader for degree {}'.format(self.DEGREE_TITLE)
                    ),
                    (
                        LOGGER_PATH,
                        'ERROR',
                        '[MISSING ORGANIZATION] Organization: invalid-organization, degree: {}'.format(
                            self.DEGREE_TITLE
                        )
                    )
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
                loader = DegreeCSVDataLoader(self.partner, csv_path=csv.name)
                loader.ingest()
                self._assert_default_logs(log_capture)
                log_capture.check_present(
                    (
                        LOGGER_PATH,
                        'ERROR',
                        'ProgramType invalid-program-type does not exist. Skipping CSV '
                        'loader for degree {}'.format(self.DEGREE_TITLE)
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
                loader = DegreeCSVDataLoader(self.partner, csv_path=csv.name)
                loader.ingest()

                self._assert_default_logs(log_capture)
                log_capture.check_present(
                    (
                        LOGGER_PATH,
                        'INFO',
                        'Degree {} is not located in the database. Creating new degree.'.format(self.DEGREE_TITLE)
                    )
                )

                assert Degree.objects.count() == 1
                assert Program.objects.count() == 1
                assert Curriculum.objects.count() == 1

                degree = Degree.objects.get(title=self.DEGREE_TITLE, partner=self.partner)
                program = Program.objects.get(degree=degree, partner=self.partner)
                curriculam = Curriculum.objects.get(program=program)

                assert degree.card_image.read() == image_content
                assert degree.specializations.count() == 2
                assert curriculam.marketing_text == self.marketing_text
                self._assert_degree_data(degree, self.BASE_EXPECTED_DEGREE_DATA)

    def test_ingest_flow_for_preexisting_degree(self, jwt_decode_patch):  # pylint: disable=unused-argument
        """
        Verify that the loader updates the existing degree in database.
        """

        self._setup_prerequisites(self.partner)
        _, image_content = self.mock_image_response()

        degree = DegreeFactory(
            title=self.DEGREE_TITLE, partner=self.partner,
            type=self.program_type
        )
        _ = DegreeAdditionalMetadataFactory(degree=degree, external_identifier='123456')

        with NamedTemporaryFile() as csv:
            csv = self._write_csv(csv, [mock_data.VALID_DEGREE_CSV_DICT])

            with LogCapture(LOGGER_PATH) as log_capture:
                loader = DegreeCSVDataLoader(self.partner, csv_path=csv.name)
                loader.ingest()

                self._assert_default_logs(log_capture)
                log_capture.check_present(
                    (
                        LOGGER_PATH,
                        'INFO',
                        'Degree {} is located in the database. Updating existing degree.'.format(self.DEGREE_TITLE)
                    )
                )
                assert Degree.objects.count() == 1
                assert Program.objects.count() == 1
                assert Curriculum.objects.count() == 1

                degree = Degree.objects.get(title=self.DEGREE_TITLE, partner=self.partner)
                program = Program.objects.get(degree=degree, partner=self.partner)
                curriculam = Curriculum.objects.get(program=program)

                assert degree.specializations.count() == 2
                assert curriculam.marketing_text == self.marketing_text
                assert degree.card_image.read() == image_content
                self._assert_degree_data(degree, self.BASE_EXPECTED_DEGREE_DATA)

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
                loader = DegreeCSVDataLoader(self.partner, csv_path=csv.name)
                loader.ingest()

                self._assert_default_logs(log_capture)
                log_capture.check_present(
                    (
                        LOGGER_PATH,
                        'INFO',
                        'Degree {} is not located in the database. Creating new degree.'.format(self.DEGREE_TITLE)
                    )
                )

                assert Degree.objects.count() == 1
                assert Program.objects.count() == 1
                assert Curriculum.objects.count() == 1

                degree = Degree.objects.get(title=self.DEGREE_TITLE, partner=self.partner)
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

    @responses.activate
    def test_image_download_failure(self, jwt_decode_patch):  # pylint: disable=unused-argument
        """
        Verify that if the course image download fails, the ingestion does not complete.
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
                loader = DegreeCSVDataLoader(self.partner, csv_path=csv.name)
                loader.ingest()

                self._assert_default_logs(log_capture)
                log_capture.check_present(
                    (
                        LOGGER_PATH,
                        'INFO',
                        'Degree {} is not located in the database. Creating new degree.'.format(self.DEGREE_TITLE)
                    )
                )

                # Creation call results in creating degree
                assert Degree.objects.count() == 1

                log_capture.check_present(
                    (
                        LOGGER_PATH,
                        'ERROR',
                        'Unexpected error happened while downloading image for degree {}'.format(self.DEGREE_TITLE)
                    ),
                    (
                        LOGGER_PATH,
                        'ERROR',
                        '[OVERRIDE IMAGE DOWNLOAD FAILURE] degree {}'.format(self.DEGREE_TITLE)
                    )
                )
