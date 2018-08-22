import pytest
from django.contrib.auth.models import Group
from django.test import RequestFactory
from django.urls import reverse

from course_discovery.apps.api.v1.tests.test_views.mixins import SerializationMixin
from course_discovery.apps.core.tests.factories import USER_PASSWORD, UserFactory
from course_discovery.apps.course_metadata.tests.factories import PathwayFactory, ProgramFactory


@pytest.mark.django_db
@pytest.mark.usefixtures('django_cache')
class TestPathwayViewSet(SerializationMixin):
    client = None
    django_assert_num_queries = None
    list_path = reverse('api:v1:pathway-list')
    partner = None
    request = None
    program = None

    @pytest.fixture(autouse=True)
    def setup(self, client, django_assert_num_queries, partner):
        user = UserFactory(is_staff=True, is_superuser=True)
        internal_test_group = Group.objects.create(name='internal-test')
        user.groups.add(internal_test_group)

        client.login(username=user.username, password=USER_PASSWORD)

        site = partner.site
        request = RequestFactory(SERVER_NAME=site.domain).get('')
        request.site = site
        request.user = user

        self.client = client
        self.django_assert_num_queries = django_assert_num_queries
        self.partner = partner
        self.request = request

    def test_pathway_list(self):
        pathways = []
        for _ in range(4):
            pathway = PathwayFactory(partner=self.partner)
            program = ProgramFactory(partner=pathway.partner)
            pathway.programs.add(program)
            pathways.append(pathway)
        response = self.client.get(self.list_path)
        assert response.status_code == 200
        assert response.data['results'] == self.serialize_pathway(pathways, many=True)

    def test_only_matching_partner(self):
        pathway = PathwayFactory(partner=self.partner)
        pathway.programs.add(ProgramFactory(partner=pathway.partner))

        non_partner_pathway = PathwayFactory()
        non_partner_pathway.programs.add(ProgramFactory(partner=non_partner_pathway.partner))

        response = self.client.get(self.list_path)
        assert response.status_code == 200
        assert response.data['results'] == self.serialize_pathway([pathway], many=True)
