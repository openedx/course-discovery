from unittest import mock

import pytest
import responses
from django.core.management import call_command

from course_discovery.apps.course_metadata.tests.factories import CourseFactory


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

    def assert_course_has_no_image(self, course):
        course.refresh_from_db()
        assert not bool(course.image)

    @responses.activate
    def test_download(self):
        image_url, image_content = self.mock_image_response()
        course = CourseFactory(card_image_url=image_url, image=None)

        call_command('download_course_images')

        assert len(responses.calls) == 1

        course.refresh_from_db()
        assert course.image.read() == image_content

    @responses.activate
    def test_download_with_overwrite_of_existing_data(self):
        image_url, image_content = self.mock_image_response()
        course = CourseFactory(card_image_url=image_url)
        assert course.image.read() != image_content

        call_command('download_course_images', '--overwrite')

        assert len(responses.calls) == 1

        course.refresh_from_db()
        assert course.image.read() == image_content

    @responses.activate
    def test_download_with_invalid_content_type(self):
        content_type = 'text/plain'
        image_url, __ = self.mock_image_response(content_type=content_type)
        course = CourseFactory(card_image_url=image_url, image=None)

        with mock.patch(self.LOGGER_PATH) as mock_logger:
            call_command('download_course_images')
            mock_logger.error.assert_called_with(
                'Image retrieved for course [%s] from [%s] has an unknown content type [%s] and will not be saved.',
                course.key,
                image_url,
                content_type
            )

        assert len(responses.calls) == 1
        self.assert_course_has_no_image(course)

    @responses.activate
    def test_download_with_invalid_status_code(self):
        status = 500
        body = b'Oops!'
        image_url, __ = self.mock_image_response(status=status, body=body)
        course = CourseFactory(card_image_url=image_url, image=None)

        with mock.patch(self.LOGGER_PATH) as mock_logger:
            call_command('download_course_images')
            mock_logger.error.assert_called_with(
                'Failed to download image for course [%s] from [%s]! Response was [%d]:\n%s',
                course.key,
                image_url,
                status,
                body
            )

        assert len(responses.calls) == 1
        self.assert_course_has_no_image(course)

    def test_download_without_courses(self):
        with mock.patch(self.LOGGER_PATH) as mock_logger:
            call_command('download_course_images')
            mock_logger.info.assert_called_with('All courses are up to date.')

    @responses.activate
    def test_download_with_unexpected_error(self):
        image_url, __ = self.mock_image_response()
        course = CourseFactory(card_image_url=image_url, image=None)

        with mock.patch('stdimage.models.StdImageFieldFile.save', side_effect=Exception) as mock_save:
            with mock.patch(self.LOGGER_PATH) as mock_logger:
                call_command('download_course_images')
                mock_logger.exception.assert_called_once_with(
                    'An unknown exception occurred while downloading image for course [%s]',
                    course.key
                )

            mock_save.assert_called_once()

        assert len(responses.calls) == 1
        self.assert_course_has_no_image(course)
