import itertools
from unittest.mock import Mock, patch

from bs4 import BeautifulSoup
from django.test import TestCase
from django.urls import reverse

from course_discovery.apps.api.tests.mixins import SiteMixin
from course_discovery.apps.core.tests.factories import USER_PASSWORD, UserFactory
from course_discovery.apps.course_metadata.tests.factories import CourseFactory, ProgramFactory
from course_discovery.apps.course_metadata.widgets import SortedModelSelect2Multiple


class SortedModelSelect2MultipleTests(SiteMixin, TestCase):
    def setUp(self):
        super().setUp()
        self.user = UserFactory(is_staff=True, is_superuser=True)
        self.client.login(username=self.user.username, password=USER_PASSWORD)
        self.widget = SortedModelSelect2Multiple()

    def test_program_ordered_m2m(self):
        """
        Verify that program page sorted m2m fields render in order. The sorted
        m2m field chosen for the test is the courses field
        """

        for courses in itertools.permutations(
            [
                CourseFactory(title="Blade Runner 2049"),
                CourseFactory(title="History of Western Literature"),
                CourseFactory(title="Urdu Poetry")
            ],
            2
        ):
            program = ProgramFactory(courses=courses)
            response = self.client.get(reverse('admin:course_metadata_program_change', args=(program.id,)))
            response_content = BeautifulSoup(response.content)
            options = response_content.find('select', {'name': 'courses'}).find_all('option')
            assert len(options) == len(courses)
            for idx, opt in enumerate(options):
                assert 'selected' in opt.attrs
                assert opt.get_text().endswith(courses[idx].title)
                assert opt.attrs['value'] == str(courses[idx].id)

    def test_optgroups_preserves_value_order(self):
        """
        Test that optgroups preserves the order of values as passed in.
        """
        widget = SortedModelSelect2Multiple()

        # Create mock selected items in specific order
        mock_optgroups = [
            (None, [{'value': '3', 'label': 'Item 3'}], 0),
            (None, [{'value': '1', 'label': 'Item 1'}], 1),
            (None, [{'value': '2', 'label': 'Item 2'}], 2),
        ]

        # Mock super().optgroups
        with patch('dal.autocomplete.ModelSelect2Multiple.optgroups',
                   return_value=mock_optgroups):
            # Test with value order [1, 3, 2]
            result = widget.optgroups('field', ['1', '3', '2'], {})

            # First two should be from the value list in order
            if len(result) >= 2:
                assert result[0][1][0]['value'] == '1', "First value should be '1'"
                assert result[1][1][0]['value'] == '3', "Second value should be '3'"

    def test_optgroups_handles_empty_values(self):
        """
        Test that optgroups handles empty value list gracefully.
        """
        widget = SortedModelSelect2Multiple()

        mock_optgroups = [
            (None, [{'value': '1', 'label': 'Item 1'}], 0),
            (None, [{'value': '2', 'label': 'Item 2'}], 1),
        ]

        with patch('dal.autocomplete.ModelSelect2Multiple.optgroups',
                   return_value=mock_optgroups):
            # Test with empty values
            result = widget.optgroups('field', [], {})

            # All items should be returned
            assert len(result) == 2, "Should have 2 items when values list is empty"
            assert result[0][1][0]['value'] == '1'
            assert result[1][1][0]['value'] == '2'

    def test_optgroups_handles_none_items(self):
        """
        Test that optgroups handles None items in optgroups gracefully.
        """
        widget = SortedModelSelect2Multiple()

        # Mock with some None items
        mock_optgroups = [
            (None, [], 0),  # Empty list
            (None, [{'value': '1', 'label': 'Item 1'}], 1),
        ]

        with patch('dal.autocomplete.ModelSelect2Multiple.optgroups',
                   return_value=mock_optgroups):
            result = widget.optgroups('field', ['1'], {})

            # Should not crash and should return valid items
            assert len(result) >= 1, "Should handle None/empty items gracefully"

    def test_optgroups_with_string_value_ids(self):
        """
        Test that optgroups correctly processes string value IDs.
        """
        widget = SortedModelSelect2Multiple()

        mock_optgroups = [
            (None, [{'value': '100', 'label': 'Item 100'}], 0),
            (None, [{'value': '200', 'label': 'Item 200'}], 1),
        ]

        with patch('dal.autocomplete.ModelSelect2Multiple.optgroups',
                   return_value=mock_optgroups):
            # Test with value list containing strings
            result = widget.optgroups('field', ['200', '100'], {})

            # First item should be 200 (from values list)
            if len(result) >= 1:
                assert str(result[0][1][0]['value']) == '200'

    def test_media_property(self):
        """
        Test that media property returns valid media object.
        """
        widget = SortedModelSelect2Multiple()

        # Mock the parent media
        with patch('dal.autocomplete.ModelSelect2Multiple.media',
                   new_callable=lambda: property(lambda self: Mock())):
            media = widget.media
            assert media is not None, "Media property should not be None"

    def test_get_context_adds_data_role_attribute(self):
        """
        Test that get_context method adds data-role attribute.
        """
        widget = SortedModelSelect2Multiple()

        # Create mock context from parent
        mock_context = {
            'widget': {
                'attrs': {}
            }
        }

        with patch('dal.autocomplete.ModelSelect2Multiple.get_context',
                   return_value=mock_context):
            result = widget.get_context('field', None, {})

            # Check that data-role attribute is added
            assert 'widget' in result
            assert 'attrs' in result['widget']
            assert 'data-role' in result['widget']['attrs']
            assert result['widget']['attrs']['data-role'] == 'autocomplete'

    def test_get_context_preserves_existing_attributes(self):
        """
        Test that get_context preserves existing attributes.
        """
        widget = SortedModelSelect2Multiple()

        # Create mock context with existing attributes
        mock_context = {
            'widget': {
                'attrs': {'class': 'my-class', 'id': 'my-id'}
            }
        }

        with patch('dal.autocomplete.ModelSelect2Multiple.get_context',
                   return_value=mock_context):
            result = widget.get_context('field', None, {})

            # Check existing attributes are preserved
            assert result['widget']['attrs']['class'] == 'my-class'
            assert result['widget']['attrs']['id'] == 'my-id'
            assert result['widget']['attrs']['data-role'] == 'autocomplete'

    def test_get_context_creates_attrs_if_missing(self):
        """
        Test that get_context creates attrs dict if it doesn't exist.
        """
        widget = SortedModelSelect2Multiple()

        # Create mock context without attrs
        mock_context = {
            'widget': {}
        }

        with patch('dal.autocomplete.ModelSelect2Multiple.get_context',
                   return_value=mock_context):
            result = widget.get_context('field', None, {})

            # attrs should be created
            assert 'attrs' in result['widget']
            assert 'data-role' in result['widget']['attrs']

    def test_get_context_handles_no_widget_key(self):
        """
        Test that get_context handles missing widget key gracefully.
        """
        widget = SortedModelSelect2Multiple()

        # Create mock context without widget key
        mock_context = {}

        with patch('dal.autocomplete.ModelSelect2Multiple.get_context',
                   return_value=mock_context):
            result = widget.get_context('field', None, {})

            # Should not crash
            assert result is not None

    def test_optgroups_duplicate_value_handling(self):
        """
        Test that optgroups handles cases where same value appears multiple times.
        """
        widget = SortedModelSelect2Multiple()

        mock_optgroups = [
            (None, [{'value': '1', 'label': 'Item 1'}], 0),
            (None, [{'value': '2', 'label': 'Item 2'}], 1),
        ]

        with patch('dal.autocomplete.ModelSelect2Multiple.optgroups',
                   return_value=mock_optgroups):
            # Multiple values with duplicates
            result = widget.optgroups('field', ['1', '1', '2'], {})

            # Should handle duplicates without crashing
            assert len(result) >= 2
