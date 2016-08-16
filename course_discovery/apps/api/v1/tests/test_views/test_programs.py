from django.core.urlresolvers import reverse
from rest_framework.test import APITestCase

from course_discovery.apps.api.serializers import ProgramSerializer
from course_discovery.apps.core.tests.factories import USER_PASSWORD, UserFactory
from course_discovery.apps.course_metadata.models import Program
from course_discovery.apps.course_metadata.tests.factories import ProgramFactory, ProgramTypeFactory


class ProgramViewSetTests(APITestCase):
    list_path = reverse('api:v1:program-list')

    def setUp(self):
        super(ProgramViewSetTests, self).setUp()
        self.user = UserFactory(is_staff=True, is_superuser=True)
        self.client.login(username=self.user.username, password=USER_PASSWORD)
        self.program = ProgramFactory()

    def test_authentication(self):
        """ Verify the endpoint requires the user to be authenticated. """
        response = self.client.get(self.list_path)
        self.assertEqual(response.status_code, 200)

        self.client.logout()
        response = self.client.get(self.list_path)
        self.assertEqual(response.status_code, 403)

    def test_get(self):
        """ Verify the endpoint returns the details for a single program. """
        url = reverse('api:v1:program-detail', kwargs={'uuid': self.program.uuid})

        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data, ProgramSerializer(self.program).data)

    def test_list(self):
        """ Verify the endpoint returns a list of all programs. """
        ProgramFactory.create_batch(3)

        response = self.client.get(self.list_path)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['results'], ProgramSerializer(Program.objects.all(), many=True).data)

    def test_filter_by_type(self):
        """ Verify that the endpoint filters programs to those of a given type. """
        url = self.list_path + '?type='

        self.program.type = ProgramTypeFactory(name='Foo')
        self.program.save()  # pylint: disable=no-member

        response = self.client.get(url + 'foo')
        self.assertEqual(response.data['results'][0], ProgramSerializer(Program.objects.get()).data)

        response = self.client.get(url + 'bar')
        self.assertEqual(response.data['results'], [])

    def test_filter_by_uuids(self):
        """ Verify that the endpoint filters programs to those matching the provided UUIDs. """
        url = self.list_path + '?uuids='

        programs = [ProgramFactory(), self.program]
        uuids = [str(p.uuid) for p in programs]

        # Create a third program, which should be filtered out.
        ProgramFactory()

        response = self.client.get(url + ','.join(uuids))
        self.assertEqual(response.data['results'], ProgramSerializer(programs, many=True).data)
