import itertools

from bs4 import BeautifulSoup
from django.test import TestCase
from django.urls import reverse

from course_discovery.apps.api.tests.mixins import SiteMixin
from course_discovery.apps.core.tests.factories import USER_PASSWORD, UserFactory
from course_discovery.apps.course_metadata.tests.factories import CourseFactory, ProgramFactory


class SortedModelSelect2MultipleTests(SiteMixin, TestCase):
    def setUp(self):
        super().setUp()
        self.user = UserFactory(is_staff=True, is_superuser=True)
        self.client.login(username=self.user.username, password=USER_PASSWORD)

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
