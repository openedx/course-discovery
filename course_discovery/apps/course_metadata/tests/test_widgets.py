import ddt
from django.test import TestCase

from course_discovery.apps.course_metadata.widgets import SortedModelSelect2Multiple


@ddt.ddt
class SortedModelSelect2MultipleTests(TestCase):
    @ddt.data(
        (['1', '2'], [1, 2, 3]),
        (['2', '1'], [2, 1, 3]),
        (['3'], [3, 1, 2]),
    )
    @ddt.unpack
    def test_optgroups_are_sorted(self, value, result_order):
        choices = ((1, 'one'), (2, 'two'), (3, 'three'))
        widget = SortedModelSelect2Multiple(url='requiredurl', choices=choices)
        result = widget.optgroups('test', value)
        self.assertEqual(result_order, [x[1][0]['value'] for x in result])
