from course_discovery.apps.api.v1.tests.test_views.mixins import FuzzyInt


def test_fuzzy_int_equality():
    fuzzy_int = FuzzyInt(10, 4)

    for i in range(6):
        assert i != fuzzy_int

    for i in range(6, 15):
        assert i == fuzzy_int

    for i in range(15, 20):
        assert i != fuzzy_int
