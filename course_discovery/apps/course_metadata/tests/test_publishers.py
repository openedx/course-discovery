import json

import ddt
import mock
import pytest
import responses
from waffle.testutils import override_switch

from course_discovery.apps.core.tests.factories import PartnerFactory
from course_discovery.apps.course_metadata.choices import CourseRunStatus, ProgramStatus
from course_discovery.apps.course_metadata.exceptions import (
    AliasCreateError, AliasDeleteError, FormRetrievalError, NodeCreateError, NodeDeleteError, NodeEditError,
    NodeLookupError
)
from course_discovery.apps.course_metadata.publishers import (
    BaseMarketingSitePublisher, CourseRunMarketingSitePublisher, ProgramMarketingSitePublisher
)
from course_discovery.apps.course_metadata.tests.factories import CourseRunFactory, ProgramFactory
from course_discovery.apps.course_metadata.tests.mixins import MarketingSitePublisherTestMixin


class DummyObject:
    dummy = '2'


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

    @mock.patch.object(BaseMarketingSitePublisher, 'delete_node', return_value=None)
    def test_delete_obj(self, mock_delete_node):
        """
        Verify that object deletion looks up the corresponding node ID and then
        attempts to delete the node with that ID.
        """
        # Confirm we don't do anything if it doesn't exist
        with mock.patch.object(BaseMarketingSitePublisher, 'node_id', return_value=None) as mock_node_id:
            self.publisher.delete_obj(self.obj)
            self.assertTrue(mock_node_id.called)
            self.assertFalse(mock_delete_node.called)

        # Now the happy path
        with mock.patch.object(BaseMarketingSitePublisher, 'node_id', return_value='123') as mock_node_id:
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


@ddt.ddt
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
    @override_switch('auto_course_about_page_creation', True)
    def test_publish_obj_create_successful(
        self,
        mock_update_node_alias,
        mock_create_node,
        *args
    ):  # pylint: disable=unused-argument
        self.publisher.publish_obj(self.obj)
        mock_create_node.assert_called_with({'data': 'test', 'field_course_uuid': str(self.obj.uuid)})
        mock_update_node_alias.assert_called_with(self.obj, 'node_id', None)

    @mock.patch.object(CourseRunMarketingSitePublisher, 'node_id', return_value=None)
    @mock.patch.object(CourseRunMarketingSitePublisher, 'serialize_obj', return_value={'data': 'test'})
    @mock.patch.object(CourseRunMarketingSitePublisher, 'create_node', return_value='node1')
    @mock.patch.object(CourseRunMarketingSitePublisher, 'update_node_alias')
    @override_switch('auto_course_about_page_creation', True)
    def test_publish_obj_create_if_exists_on_discovery(
        self,
        mock_update_node_alias,
        mock_create_node,
        mock_serialize_obj,
        mock_node_id,
        *args
    ):  # pylint: disable=unused-argument
        self.publisher.publish_obj(self.obj)
        mock_node_id.assert_called_with(self.obj)
        mock_serialize_obj.assert_called_with(self.obj)
        mock_create_node.assert_called_with({'data': 'test', 'field_course_uuid': str(self.obj.uuid)})
        mock_update_node_alias.assert_called_with(self.obj, 'node1', None)

    @mock.patch.object(CourseRunMarketingSitePublisher, 'node_id', return_value='node_id')
    @mock.patch.object(CourseRunMarketingSitePublisher, 'serialize_obj', return_value='data')
    @mock.patch.object(CourseRunMarketingSitePublisher, 'edit_node', return_value=None)
    @mock.patch.object(CourseRunMarketingSitePublisher, 'update_node_alias')
    def test_publish_obj_edit(self, mock_node_alias, mock_edit_node, *args):  # pylint: disable=unused-argument
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
        mock_node_alias.assert_called_with(self.obj, 'node_id', None)

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

    @responses.activate
    def test_update_node_alias(self):
        """
        Verify that the publisher attempts to create a new alias associated with the new course_run,
        and that appropriate exceptions are raised for non-200 status codes.
        """
        # No previous object is provided. Create a new node and make sure
        # title alias created, by default, based on the title is deleted
        # and a new alias based on marketing slug is created.
        self.mock_api_client()
        self.mock_get_alias_form()
        self.mock_get_delete_form(self.obj.slug)
        self.mock_delete_alias()
        self.mock_get_delete_form(self.obj.slug)
        self.mock_add_alias()

        self.publisher.update_node_alias(self.obj, self.node_id, None)

        assert responses.calls[-1].request.url == '{}/add'.format(self.publisher.alias_api_base)

        responses.reset()

        # Same scenario, but this time a non-200 status code is returned during
        # alias creation. An exception should be raised.
        self.mock_api_client()
        self.mock_get_alias_form()
        self.mock_get_delete_form(self.obj.slug)
        self.mock_delete_alias()
        self.mock_get_delete_form(self.obj.slug)
        self.mock_add_alias(status=500)

        with pytest.raises(AliasCreateError):
            self.publisher.update_node_alias(self.obj, self.node_id, None)

        responses.reset()

        # A previous object is provided, but the marketing slug hasn't changed.
        # Neither alias creation nor alias deletion should occur.
        self.mock_api_client()
        self.mock_get_delete_form(self.obj.slug)

        self.publisher.update_node_alias(self.obj, self.node_id, self.obj)

        responses.reset()

        # In this case, similate the fact that alias form retrival returned error
        # FormRetrievalError should be raised
        self.mock_api_client()
        self.mock_get_delete_form(self.obj.slug)
        self.mock_get_alias_form(status=500)
        with pytest.raises(FormRetrievalError):
            self.publisher.update_node_alias(self.obj, self.node_id, None)

    def test_alias(self):
        """
        Verify that aliases are constructed correctly.
        """
        actual = self.publisher.alias(self.obj)
        expected = 'course/{slug}'.format(slug=self.obj.slug)

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

    @mock.patch.object(ProgramMarketingSitePublisher, 'serialize_obj', return_value={'uuid': 'foo'})
    @mock.patch.object(ProgramMarketingSitePublisher, 'node_id', return_value=None)
    @mock.patch.object(ProgramMarketingSitePublisher, 'create_node', return_value='node_id')
    @mock.patch.object(ProgramMarketingSitePublisher, 'update_node_alias', return_value=None)
    @mock.patch.object(ProgramMarketingSitePublisher, 'get_and_delete_alias', return_value=None)
    def test_publish_obj_missed_in_drupal(
            self, mock_get_and_delete_alias, mock_update_node_alias, mock_create_node, mock_node_id, _mock_serialize
    ):
        """
        Verify that the publisher correctly creates a node on drupal if for whatever reason, we think it should
        already exist, but it does not on the marketing side.
        """
        self.obj.type.name = 'Professional Certificate'
        self.publisher.publish_obj(self.obj, previous_obj=self.obj)

        self.assertTrue(mock_node_id.called)
        self.assertTrue(mock_create_node.called)
        self.assertTrue(mock_get_and_delete_alias.called)
        self.assertTrue(mock_update_node_alias.called)

    @mock.patch.object(ProgramMarketingSitePublisher, 'serialize_obj', return_value={'uuid': 'foo'})
    @mock.patch.object(ProgramMarketingSitePublisher, 'node_id', return_value='node_id')
    @mock.patch.object(ProgramMarketingSitePublisher, 'create_node', return_value='node_id')
    @mock.patch.object(ProgramMarketingSitePublisher, 'edit_node', return_value=None)
    @mock.patch.object(ProgramMarketingSitePublisher, 'update_node_alias', return_value=None)
    @mock.patch.object(ProgramMarketingSitePublisher, 'get_and_delete_alias', return_value=None)
    def test_publish_obj(
            self, mock_get_and_delete_alias, mock_update_node_alias, mock_edit_node, mock_create_node, *args
    ):  # pylint: disable=unused-argument
        """
        Verify that the publisher only attempts to publish programs of certain types,
        only attempts an edit when any one of a set of trigger fields is changed,
        and always follows publication with an attempt to update the node alias.
        """
        # Publication isn't supported for programs of this type.
        self.publisher.publish_obj(self.obj)

        mocked_methods = (mock_create_node, mock_edit_node, mock_update_node_alias)
        for mocked_method in mocked_methods:
            assert not mocked_method.called

        types_to_publish = (
            'XSeries',
            'MicroMasters',
            'Professional Certificate'
        )

        for name in types_to_publish:
            for mocked_method in mocked_methods:
                mocked_method.reset_mock()

            # Publication is supported for programs of this type. No previous object
            # is provided, so node creation should occur.
            self.obj.type.name = name
            self.publisher.publish_obj(self.obj)

            assert mock_create_node.called
            assert not mock_edit_node.called
            assert mock_get_and_delete_alias.called
            assert mock_update_node_alias.called

            for mocked_method in mocked_methods:
                mocked_method.reset_mock()

            # A previous object is provided, but none of the trigger fields have
            # changed. Editing should not occur.
            self.publisher.publish_obj(self.obj, previous_obj=self.obj)

            for mocked_method in mocked_methods:
                assert not mocked_method.called

            # Trigger fields have changed. Editing should occur.
            previous_obj = ProgramFactory()
            self.publisher.publish_obj(self.obj, previous_obj=previous_obj)

            assert not mock_create_node.called
            assert mock_edit_node.called
            assert mock_get_and_delete_alias.called
            assert mock_update_node_alias.called

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
            'type': str(self.obj.type).lower().replace(' ', '_'),
            'uuid': str(self.obj.uuid),
        }

        assert actual == expected

        self.obj.status = ProgramStatus.Unpublished

        actual = self.publisher.serialize_obj(self.obj)
        expected['status'] = 0

        assert actual == expected

    @responses.activate
    def test_update_node_alias(self):
        """
        Verify that the publisher attempts to create a new alias when necessary
        and deletes an old alias, if one existed, and that appropriate exceptions
        are raised for non-200 status codes.
        """
        # No previous object is provided. Create a new node and make sure
        # title alias created, by default, based on the title is deleted
        # and a new alias based on marketing slug is created.
        self.mock_api_client()
        self.mock_get_alias_form()
        self.mock_get_delete_form(self.obj.title)
        self.mock_delete_alias()
        self.mock_get_delete_form(self.obj.marketing_slug)
        self.mock_add_alias()

        self.publisher.update_node_alias(self.obj, self.node_id, None)

        assert responses.calls[-1].request.url == '{}/add'.format(self.publisher.alias_api_base)

        responses.reset()

        # Same scenario, but this time a non-200 status code is returned during
        # alias creation. An exception should be raised.
        self.mock_api_client()
        self.mock_get_alias_form()
        self.mock_get_delete_form(self.obj.title)
        self.mock_delete_alias()
        self.mock_get_delete_form(self.obj.marketing_slug)
        self.mock_add_alias(status=500)

        with pytest.raises(AliasCreateError):
            self.publisher.update_node_alias(self.obj, self.node_id, None)

        responses.reset()

        # A previous object is provided, but the marketing slug hasn't changed.
        # Neither alias creation nor alias deletion should occur.
        self.mock_api_client()
        self.mock_get_delete_form(self.obj.marketing_slug)

        self.publisher.update_node_alias(self.obj, self.node_id, self.obj)

        responses.reset()

        # A previous object is provided, and the marketing slug has changed.
        # Both alias creation and alias deletion should occur.
        previous_obj = ProgramFactory()

        self.mock_api_client()
        self.mock_get_delete_form(self.obj.marketing_slug)
        self.mock_get_delete_form(previous_obj.marketing_slug)
        self.mock_delete_alias_form()
        self.mock_delete_alias()
        self.mock_get_alias_form()
        self.mock_get_delete_form(self.obj.marketing_slug)
        self.mock_add_alias()

        self.publisher.update_node_alias(self.obj, self.node_id, previous_obj)

        assert any('/add' in call.request.url for call in responses.calls)
        assert any('/list/{}'.format(previous_obj.marketing_slug) in call.request.url for call in responses.calls)

        responses.reset()

        # Same scenario, but this time a non-200 status code is returned during
        # alias deletion. An exception should be raised.
        self.mock_api_client()
        self.mock_get_delete_form(self.obj.marketing_slug)
        self.mock_get_delete_form(previous_obj.marketing_slug)
        self.mock_delete_alias_form()
        self.mock_delete_alias(status=500)

        with pytest.raises(AliasDeleteError):
            self.publisher.update_node_alias(self.obj, self.node_id, previous_obj)

    def test_alias(self):
        """
        Verify that aliases are constructed correctly.
        """
        actual = self.publisher.alias(self.obj)
        expected = '{type}/{slug}'.format(type=self.obj.type.slug, slug=self.obj.marketing_slug)

        assert actual == expected
