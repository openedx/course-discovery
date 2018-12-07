import mock
import pytest
import responses
from django.core.files.base import ContentFile
from django.core.management import call_command

from course_discovery.apps.course_metadata.tests import factories


@pytest.mark.django_db
class TestDownloadDrupalInstructorImage():
    LOGGER_PATH = 'course_discovery.apps.course_metadata.management.commands.download_drupal_instructor_image.logger'

    def _mock_image_response(self, status=200, body=None, content_type='image/jpeg'):
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

    def _setup_person_with_image(self):
        image_url, _ = self._mock_image_response()
        person = factories.PersonFactory(profile_image_url=image_url)
        return person

    def _configutation(self, person_uuids=None):
        if person_uuids:
            person_uuids = ','.join(person_uuids)
            factories.ProfileImageDownloadConfigFactory(
                person_uuids=person_uuids
            )

    @responses.activate
    def test_single_person_download(self):
        person = self._setup_person_with_image()
        self._configutation([str(person.uuid)])

        call_command('download_drupal_instructor_image')

        assert len(responses.calls) == 1

        person.refresh_from_db()
        assert person.profile_image.url == person.profile_image_url  # pylint: disable=no-member

    @responses.activate
    def test_image_already_downloaded(self):
        _, image_content = self._mock_image_response()
        person = factories.PersonFactory(
            profile_image=ContentFile(image_content, name='tmp.png')
        )
        self._configutation([str(person.uuid)])

        # In the application code when a user uploads an image in Publisher UI
        # the profile_image_url will be set to the profile_image.url.
        person.profile_image_url = person.profile_image.url  # pylint: disable=no-member
        person.save()
        person.refresh_from_db()

        call_command('download_drupal_instructor_image')

        # API should not be called
        assert len(responses.calls) == 0

        person.refresh_from_db()
        assert person.profile_image.url == person.profile_image_url  # pylint: disable=no-member

    @responses.activate
    def test_image_not_found(self):
        image_url, _ = self._mock_image_response(status=404)
        person = factories.PersonFactory(profile_image_url=image_url)
        self._configutation([str(person.uuid)])

        with mock.patch(self.LOGGER_PATH) as mock_logger:
            call_command('download_drupal_instructor_image')
            mock_logger.error.assert_called_with(
                'Failed to retrieve Image for {name}, [{uuid}], at {url} with status code [{status_code}]'.format(
                    name=person.full_name,
                    uuid=person.uuid,
                    url=person.profile_image_url,
                    status_code=404
                ))
            assert len(responses.calls) == 1

            person.refresh_from_db()
            # Image would not be saved because the new image failed to download
            assert person.profile_image.url != person.profile_image_url  # pylint: disable=no-member

    @responses.activate
    def test_unknown_content_type(self):
        image_url, _ = self._mock_image_response(content_type='unknown')
        person = factories.PersonFactory(profile_image_url=image_url)
        self._configutation([str(person.uuid)])

        with mock.patch(self.LOGGER_PATH) as mock_logger:
            call_command('download_drupal_instructor_image')
            mock_logger.error.assert_called_with(
                'Unknown content type for instructor [{instructor}], [{uuid}], and url [{url}]'.format(
                    instructor=person.full_name,
                    uuid=person.uuid,
                    url=person.profile_image_url
                ))
            assert len(responses.calls) == 1

            person.refresh_from_db()
            # Image would not be saved because the new image failed to download
            assert person.profile_image.url != person.profile_image_url  # pylint: disable=no-member

    @responses.activate
    def test_image_file_not_created(self):
        person = self._setup_person_with_image()
        self._configutation([str(person.uuid)])

        with mock.patch(
            'course_discovery.apps.course_metadata.management.commands.download_drupal_instructor_image.ContentFile'
        ) as mock_content_file:
            with mock.patch(self.LOGGER_PATH) as mock_logger:
                mock_content_file.return_value = None
                call_command('download_drupal_instructor_image')
                mock_logger.error.assert_called_with(
                    'failed to create image file for Instructor {instructor}, [{uuid}], from {url}'.format(
                        instructor=person.full_name,
                        uuid=person.uuid,
                        url=person.profile_image_url
                    ))
                assert len(responses.calls) == 1

                person.refresh_from_db()
                assert person.profile_image.url != person.profile_image_url  # pylint: disable=no-member

    @responses.activate
    def test_connection_error(self):
        image_url = 'https://example.com/image.jpg'
        person = factories.PersonFactory(profile_image_url=image_url)
        self._configutation([str(person.uuid)])

        with mock.patch(self.LOGGER_PATH) as mock_logger:
            call_command('download_drupal_instructor_image')
            mock_logger.exception.assert_called_with(
                'Connection failure downloading image for {instructor}, [{uuid}], from {url}'.format(
                    instructor=person.full_name,
                    uuid=person.uuid,
                    url=person.profile_image_url
                ))

            person.refresh_from_db()
            # Image would not be saved because the new image failed to download
            assert person.profile_image.url != person.profile_image_url  # pylint: disable=no-member
