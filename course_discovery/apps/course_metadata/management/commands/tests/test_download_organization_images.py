import mock
import pytest
import responses
from django.core.management import call_command

from course_discovery.apps.course_metadata.tests.factories import OrganizationFactory


@pytest.mark.django_db
class TestDownloadCourseImages:
    LOGGER_PATH = 'course_discovery.apps.course_metadata.management.commands.download_course_images.logger'

    def mock_image_response(self, status=200, body=None, content_type='image/jpeg'):
        # PNG. Single black pixel
        body = body or b'\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x02\x00\x00\x00' \
                       b'\x90wS\xde\x00\x00\x00\x0cIDATx\x9cc```\x00\x00\x00\x04\x00\x01\xf6\x178U\x00\x00\x00\x00' \
                       b'IEND\xaeB`\x82'
        image_url = 'https://example.com/image.jpg'
        responses.add(
            responses.GET,
            image_url,
            body=body,
            status=status,
            content_type=content_type
        )
        return image_url, body

    @responses.activate
    def test_download(self):
        image_url, image_content = self.mock_image_response()
        organization = OrganizationFactory(
            logo_image=None,
            banner_image=None,
            certificate_logo_image=None,
            logo_image_url=image_url,
            banner_image_url=image_url,
            certificate_logo_image_url=image_url,
        )

        call_command('download_organization_images')

        assert len(responses.calls) == 3

        organization.refresh_from_db()

        assert organization.logo_image.read() == image_content
        assert organization.banner_image.read() == image_content
        assert organization.certificate_logo_image.read() == image_content

    def test_download_with_get_error(self):
        image_url, image_content = self.mock_image_response()
        organization = OrganizationFactory(
            logo_image_url=None,
            banner_image_url=None,
            certificate_logo_image_url=image_url,
        )

        with mock.patch('course_discovery.apps.course_metadata.management.commands.'
                        'download_organization_images.requests.get', side_effect=Exception):
            with mock.patch('course_discovery.apps.course_metadata.management.commands.'
                            'download_organization_images.logger.error') as mock_logger:
                call_command('download_organization_images')
                mock_logger.assert_called_with(
                    'Could not get [%s] for organization [%s]',
                    'certificate_logo_image',
                    organization.uuid,
                )

    def test_download_with_save_error(self):
        image_url, image_content = self.mock_image_response()
        organization = OrganizationFactory(
            logo_image_url=None,
            banner_image_url=None,
            certificate_logo_image_url=image_url,
        )

        with mock.patch('course_discovery.apps.course_metadata.management.commands.'
                        'download_organization_images.ContentFile', side_effect=Exception):
            with mock.patch('course_discovery.apps.course_metadata.management.commands.'
                            'download_organization_images.logger.error') as mock_logger:
                call_command('download_organization_images')
                mock_logger.assert_called_with(
                    'Could not set [%s] for organization [%s]',
                    'certificate_logo_image',
                    organization.uuid,
                )
