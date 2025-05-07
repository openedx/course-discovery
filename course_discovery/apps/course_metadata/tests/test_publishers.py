import json

import mock
import pytest
import responses

from course_discovery.apps.core.tests.factories import PartnerFactory
from course_discovery.apps.course_metadata.choices import CourseRunStatus, ProgramStatus
from course_discovery.apps.course_metadata.exceptions import (
    AliasCreateError, AliasDeleteError, FormRetrievalError, NodeCreateError, NodeDeleteError, NodeEditError,
    NodeLookupError
)
from course_discovery.apps.course_metadata.publishers import (
    BaseMarketingSitePublisher, CourseRunMarketingSitePublisher, ProgramMarketingSitePublisher
)
from course_discovery.apps.course_metadata.tests import toggle_switch
from course_discovery.apps.course_metadata.tests.factories import CourseRunFactory, ProgramFactory
from course_discovery.apps.course_metadata.tests.mixins import MarketingSitePublisherTestMixin


class DummyObject:
    dummy = 2


class BaseMarketingSitePublisherTests(MarketingSitePublisherTestMixin):
    """
    Tests covering shared publishing logic.
    """
    def setUp(self):
        super().setUp()

        self.partner = PartnerFactory()
        self.publisher = BaseMarketingSitePublisher(self.partner)
        self.publisher.unique_field = 'dummy'
        self.publisher.node_lookup_field = 'field_dummy'

        self.api_root = self.publisher.client.api_url
        self.username = self.publisher.client.username

        self.obj = DummyObject()

    def test_publish_obj(self):
        """
        Verify that the base publisher doesn't implement this method.
        """
        with pytest.raises(NotImplementedError):
            self.publisher.publish_obj(self.obj)

    @mock.patch.object(BaseMarketingSitePublisher, 'node_id', return_value='123')
    @mock.patch.object(BaseMarketingSitePublisher, 'delete_node', return_value=None)
    def test_delete_obj(self, mock_delete_node, mock_node_id):
        """
        Verify that object deletion looks up the corresponding node ID and then
        attempts to delete the node with that ID.
        """
        self.publisher.delete_obj(self.obj)

        mock_node_id.assert_called_with(self.obj)
        mock_delete_node.assert_called_with('123')

    @responses.activate
    def test_serialize_obj(self):
        """
        Verify that the base publisher serializes data required to publish any object.
        """
        self.mock_api_client()

        actual = self.publisher.serialize_obj(self.obj)
        expected = {
            'field_dummy': '2',
            'author': {'id': self.user_id},
        }

        assert actual == expected

    @responses.activate
    def test_node_id(self):
        """
        Verify that node ID lookup makes a request and pulls the ID out of the
        response, and raises an exception for non-200 status codes.
        """
        self.mock_api_client()

        lookup_value = getattr(self.obj, self.publisher.unique_field)
        self.mock_node_retrieval(self.publisher.node_lookup_field, lookup_value)

        node_id = self.publisher.node_id(self.obj)

        assert responses.calls[-1].request.url == '{base}?{field}={value}'.format(
            base=self.publisher.node_api_base,
            field=self.publisher.node_lookup_field,
            value=lookup_value
        )

        assert node_id == self.node_id

        responses.reset()

        self.mock_api_client()
        self.mock_node_retrieval(self.publisher.node_lookup_field, lookup_value, status=500)

        with pytest.raises(NodeLookupError):
            self.publisher.node_id(self.obj)

        responses.reset()
        self.mock_api_client()
        self.mock_node_retrieval(self.publisher.node_lookup_field, lookup_value, exists=False)
        node_id = self.publisher.node_id(self.obj)
        assert node_id is None

    @responses.activate
    def test_create_node(self):
        """
        Verify that node creation makes the correct request and returns the ID
        contained in the response, and raises an exception for non-201 status codes.
        """
        self.mock_api_client()

        response_data = {'id': self.node_id}
        self.mock_node_create(response_data, 201)

        node_data = {'foo': 'bar'}
        node_id = self.publisher.create_node(node_data)

        assert responses.calls[-1].request.url == self.publisher.node_api_base
        assert json.loads(responses.calls[-1].request.body) == node_data
        assert node_id == self.node_id

        responses.reset()

        self.mock_api_client()
        self.mock_node_create(response_data, 500)

        with pytest.raises(NodeCreateError):
            self.publisher.create_node(node_data)

    @responses.activate
    def test_edit_node(self):
        """
        Verify that node editing makes the correct request and raises an exception
        for non-200 status codes.
        """
        self.mock_api_client()
        self.mock_node_edit(200)

        node_data = {'foo': 'bar'}
        self.publisher.edit_node(self.node_id, node_data)

        assert responses.calls[-1].request.url == '{base}/{node_id}'.format(
            base=self.publisher.node_api_base,
            node_id=self.node_id
        )
        assert json.loads(responses.calls[-1].request.body) == node_data

        responses.reset()

        self.mock_api_client()
        self.mock_node_edit(500)

        with pytest.raises(NodeEditError):
            self.publisher.edit_node(self.node_id, node_data)

    @responses.activate
    def test_delete_node(self):
        """
        Verify that node deletion makes the correct request and raises an exception
        for non-204 status codes.
        """
        self.mock_api_client()
        self.mock_node_delete(200)

        self.publisher.delete_node(self.node_id)

        assert responses.calls[-1].request.url == '{base}/{node_id}'.format(
            base=self.publisher.node_api_base,
            node_id=self.node_id
        )

        responses.reset()

        self.mock_api_client()
        self.mock_node_delete(500)

        with pytest.raises(NodeDeleteError):
            self.publisher.delete_node(self.node_id)


class CourseRunMarketingSitePublisherTests(MarketingSitePublisherTestMixin):
    """
    Tests covering course run-specific publishing logic.
    """
    def setUp(self):
        super().setUp()

        self.partner = PartnerFactory()
        self.publisher = CourseRunMarketingSitePublisher(self.partner)

        self.api_root = self.publisher.client.api_url
        self.username = self.publisher.client.username

        self.obj = CourseRunFactory()

    @mock.patch.object(CourseRunMarketingSitePublisher, 'node_id', return_value=None)
    @mock.patch.object(CourseRunMarketingSitePublisher, 'create_node')
    def test_publish_obj_create_disabled(self, mock_create_node, mock_node_id):
        self.publisher.publish_obj(self.obj)
        mock_node_id.assert_called_with(self.obj)
        assert not mock_create_node.called

    @mock.patch.object(CourseRunMarketingSitePublisher, 'serialize_obj', return_value={'data': 'test'})
    @mock.patch.object(CourseRunMarketingSitePublisher, 'node_id', return_value=None)
    @mock.patch.object(CourseRunMarketingSitePublisher, 'create_node', return_value='node_id')
    @mock.patch.object(CourseRunMarketingSitePublisher, 'update_node_alias')
    def test_publish_obj_create_successful(
        self,
        mock_update_node_alias,
        mock_create_node,
        *args
    ):  # pylint: disable=unused-argument
        toggle_switch('auto_course_about_page_creation', True)
        self.publisher.publish_obj(self.obj)
        mock_create_node.assert_called_with({'data': 'test', 'field_course_uuid': str(self.obj.uuid)})
        mock_update_node_alias.assert_called_with(self.obj, 'node_id', None)

    @mock.patch.object(CourseRunMarketingSitePublisher, 'node_id', return_value=None)
    @mock.patch.object(CourseRunMarketingSitePublisher, 'serialize_obj', return_value={'data': 'test'})
    @mock.patch.object(CourseRunMarketingSitePublisher, 'create_node', return_value='node1')
    @mock.patch.object(CourseRunMarketingSitePublisher, 'update_node_alias')
    def test_publish_obj_create_if_exists_on_discovery(
        self,
        mock_update_node_alias,
        mock_create_node,
        mock_serialize_obj,
        mock_node_id,
        *args
    ):  # pylint: disable=unused-argument
        toggle_switch('auto_course_about_page_creation', True)
        self.publisher.publish_obj(self.obj, previous_obj=self.obj)
        mock_node_id.assert_called_with(self.obj)
        mock_serialize_obj.assert_called_with(self.obj)
        mock_create_node.assert_called_with({'data': 'test', 'field_course_uuid': str(self.obj.uuid)})
        mock_update_node_alias.assert_called_with(self.obj, 'node1', self.obj)

    @mock.patch.object(CourseRunMarketingSitePublisher, 'node_id', return_value='node_id')
    @mock.patch.object(CourseRunMarketingSitePublisher, 'serialize_obj', return_value='data')
    @mock.patch.object(CourseRunMarketingSitePublisher, 'edit_node', return_value=None)
    def test_publish_obj_edit(self, mock_edit_node, *args):  # pylint: disable=unused-argument
        """
        Verify that the publisher attempts to publish when course run status changes.
        """

        # A previous object is provided, but the status hasn't changed.
        # No editing should occur.
        self.publisher.publish_obj(self.obj, previous_obj=self.obj)
        assert not mock_edit_node.called

        # A previous object is provided, and the status has changed.
        # Editing should occur.
        previous_obj = CourseRunFactory(status=CourseRunStatus.Unpublished)
        self.publisher.publish_obj(self.obj, previous_obj=previous_obj)
        mock_edit_node.assert_called_with('node_id', 'data')

    @responses.activate
    def test_serialize_obj(self):
        """
        Verify that the publisher serializes data required to publish course runs.
        """
        self.mock_api_client()

        actual = self.publisher.serialize_obj(self.obj)
        expected = {
            'field_course_id': self.obj.key,
            'title': self.obj.title,
            'author': {'id': self.user_id},
            'status': 1,
            'type': 'course',
        }

        assert actual == expected

        self.obj.status = CourseRunStatus.Unpublished

        actual = self.publisher.serialize_obj(self.obj)
        expected['status'] = 0

        assert actual == expected


class ProgramMarketingSitePublisherTests(MarketingSitePublisherTestMixin):
    """
    Tests covering program-specific publishing logic.
    """
    def setUp(self):
        super().setUp()

        self.partner = PartnerFactory()
        self.publisher = ProgramMarketingSitePublisher(self.partner)

        self.api_root = self.publisher.client.api_url
        self.username = self.publisher.client.username

        self.obj = ProgramFactory()

    @responses.activate
    def test_serialize_obj(self):
        """
        Verify that the publisher serializes data required to publish programs.
        """
        self.mock_api_client()

        actual = self.publisher.serialize_obj(self.obj)
        expected = {
            'field_uuid': str(self.obj.uuid),
            'author': {'id': self.user_id},
            'status': 1,
            'title': self.obj.title,
            'uuid': str(self.obj.uuid),
        }

        assert actual == expected

        self.obj.status = ProgramStatus.Unpublished

        actual = self.publisher.serialize_obj(self.obj)
        expected['status'] = 0

        assert actual == expected
