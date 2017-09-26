import datetime
import json

import mock
import pytest
import responses
from freezegun import freeze_time
from slumber.exceptions import HttpServerError
from waffle.testutils import override_switch

from course_discovery.apps.core.models import Partner
from course_discovery.apps.course_metadata.tests.factories import CourseRunFactory as DiscoveryCourseRunFactory
from course_discovery.apps.course_metadata.tests.factories import OrganizationFactory
from course_discovery.apps.publisher.studio_api_utils import StudioAPI
from course_discovery.apps.publisher.tests.factories import CourseRunFactory


@freeze_time('2017-01-01T00:00:00Z')
@pytest.mark.django_db
class TestSignals:
    @override_switch('enable_publisher_create_course_run_in_studio', active=True)
    def test_create_course_run_in_studio_without_partner(self):
        with mock.patch('course_discovery.apps.publisher.signals.logger.error') as mock_logger:
            publisher_course_run = CourseRunFactory(course__organizations=[])

            assert publisher_course_run.course.partner is None
            mock_logger.assert_called_with(
                'Failed to publish course run [%d] to Studio. Related course [%d] has no associated Partner.',
                publisher_course_run.id,
                publisher_course_run.course.id
            )

    @responses.activate
    @mock.patch.object(Partner, 'access_token', return_value='JWT fake')
    @override_switch('enable_publisher_create_course_run_in_studio', active=True)
    def test_create_course_run_in_studio(self, mock_access_token):  # pylint: disable=unused-argument
        organization = OrganizationFactory()
        partner = organization.partner
        start = datetime.datetime.utcnow()
        course_run_key = 'course-v1:TestX+Testing101x+1T2017'

        body = {'id': course_run_key}
        studio_url_root = partner.studio_url.strip('/')
        url = '{}/api/v1/course_runs/'.format(studio_url_root)
        responses.add(responses.POST, url, json=body, status=200)

        body = {'card_image': 'https://example.com/image.jpg'}
        url = '{root}/api/v1/course_runs/{course_run_key}/images/'.format(
            root=studio_url_root,
            course_run_key=course_run_key
        )
        responses.add(responses.POST, url, json=body, status=200)

        publisher_course_run = CourseRunFactory(start=start, lms_course_id=None, course__organizations=[organization])

        # We refresh because the signal should update the instance with the course run key from Studio
        publisher_course_run.refresh_from_db()

        assert len(responses.calls) == 2
        assert publisher_course_run.lms_course_id == course_run_key

    @responses.activate
    @mock.patch.object(Partner, 'access_token', return_value='JWT fake')
    @override_switch('enable_publisher_create_course_run_in_studio', active=True)
    def test_create_course_run_in_studio_as_rerun(self, mock_access_token):  # pylint: disable=unused-argument
        number = 'TestX'
        organization = OrganizationFactory()
        partner = organization.partner
        course_key = '{org}+{number}'.format(org=organization.key, number=number)
        discovery_course_run = DiscoveryCourseRunFactory(course__partner=partner, course__key=course_key)
        start = datetime.datetime.utcnow()
        course_run_key = 'course-v1:TestX+Testing101x+1T2017'

        body = {'id': course_run_key}
        studio_url_root = partner.studio_url.strip('/')
        url = '{root}/api/v1/course_runs/{course_run_key}/rerun/'.format(
            root=studio_url_root,
            course_run_key=discovery_course_run.key
        )
        responses.add(responses.POST, url, json=body, status=200)

        body = {'card_image': 'https://example.com/image.jpg'}
        url = '{root}/api/v1/course_runs/{course_run_key}/images/'.format(
            root=studio_url_root,
            course_run_key=course_run_key
        )
        responses.add(responses.POST, url, json=body, status=200)

        publisher_course_run = CourseRunFactory(
            start=start,
            lms_course_id=None,
            course__organizations=[organization],
            course__number=number
        )

        # We refresh because the signal should update the instance with the course run key from Studio
        publisher_course_run.refresh_from_db()

        assert len(responses.calls) == 2
        assert publisher_course_run.lms_course_id == course_run_key

    @responses.activate
    @mock.patch.object(Partner, 'access_token', return_value='JWT fake')
    @mock.patch.object(StudioAPI, 'update_course_run_image_in_studio', side_effect=Exception)
    @override_switch('enable_publisher_create_course_run_in_studio', active=True)
    def test_create_course_run_in_studio_with_image_failure(self, __, ___):  # pylint: disable=unused-argument
        organization = OrganizationFactory()
        partner = organization.partner
        start = datetime.datetime.utcnow()
        course_run_key = 'course-v1:TestX+Testing101x+1T2017'

        body = {'id': course_run_key}
        studio_url_root = partner.studio_url.strip('/')
        url = '{}/api/v1/course_runs/'.format(studio_url_root)
        responses.add(responses.POST, url, json=body, status=200)

        with mock.patch('course_discovery.apps.publisher.signals.logger.exception') as mock_logger:
            publisher_course_run = CourseRunFactory(
                start=start,
                lms_course_id=None,
                course__organizations=[organization]
            )

        assert len(responses.calls) == 1
        assert publisher_course_run.lms_course_id == course_run_key

        mock_logger.assert_called_with('Failed to update Studio image for course run [%s]', course_run_key)

    # pylint: disable=unused-argument
    @responses.activate
    @mock.patch.object(Partner, 'access_token', return_value='JWT fake')
    @override_switch('enable_publisher_create_course_run_in_studio', active=True)
    def test_create_course_run_in_studio_with_image_api_failure(self, mock_access_token):
        organization = OrganizationFactory()
        partner = organization.partner
        start = datetime.datetime.utcnow()
        course_run_key = 'course-v1:TestX+Testing101x+1T2017'

        body = {'id': course_run_key}
        studio_url_root = partner.studio_url.strip('/')
        url = '{}/api/v1/course_runs/'.format(studio_url_root)
        responses.add(responses.POST, url, json=body, status=200)

        body = {'error': 'Server error'}
        url = '{root}/api/v1/course_runs/{course_run_key}/images/'.format(
            root=studio_url_root,
            course_run_key=course_run_key
        )
        responses.add(responses.POST, url, json=body, status=500)

        with mock.patch('course_discovery.apps.publisher.signals.logger.exception') as mock_logger:
            publisher_course_run = CourseRunFactory(
                start=start,
                lms_course_id=None,
                course__organizations=[organization]
            )

        assert len(responses.calls) == 2
        assert publisher_course_run.lms_course_id == course_run_key

        mock_logger.assert_called_with(
            'Failed to update Studio image for course run [%s]: %s', course_run_key, json.dumps(body).encode('utf8')
        )

    @responses.activate
    @mock.patch.object(Partner, 'access_token', return_value='JWT fake')
    @override_switch('enable_publisher_create_course_run_in_studio', active=True)
    def test_create_course_run_in_studio_with_api_failure(self, mock_access_token):  # pylint: disable=unused-argument
        organization = OrganizationFactory()
        partner = organization.partner

        body = {'error': 'Server error'}
        studio_url_root = partner.studio_url.strip('/')
        url = '{}/api/v1/course_runs/'.format(studio_url_root)
        responses.add(responses.POST, url, json=body, status=500)

        with mock.patch('course_discovery.apps.publisher.signals.logger.exception') as mock_logger:
            with pytest.raises(HttpServerError):
                publisher_course_run = CourseRunFactory(lms_course_id=None, course__organizations=[organization])

                assert len(responses.calls) == 1
                assert publisher_course_run.lms_course_id is None

                mock_logger.assert_called_with(
                    'Failed to create course run [%d] on Studio: %s',
                    publisher_course_run.id,
                    json.dumps(body).encode('utf8')
                )
