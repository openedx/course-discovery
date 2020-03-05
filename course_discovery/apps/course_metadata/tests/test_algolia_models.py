import pytest
from django.conf import settings
from django.contrib.sites.models import Site
from django.test import TestCase

from conftest import TEST_DOMAIN
from course_discovery.apps.core.models import Partner
from course_discovery.apps.core.tests.factories import PartnerFactory, SiteFactory
from course_discovery.apps.course_metadata.algolia_proxy_models import AlgoliaProxyCourse, AlgoliaProxyProgram
from course_discovery.apps.course_metadata.tests.factories import CourseFactory, OrganizationFactory, ProgramFactory


class AlgoliaProxyCourseFactory(CourseFactory):
    class Meta:
        model = AlgoliaProxyCourse


class AlgoliaProxyProgramFactory(ProgramFactory):
    class Meta:
        model = AlgoliaProxyProgram


class TestAlgoliaProxyWithEdxPartner(TestCase):
    @classmethod
    def setUpClass(cls):
        super(TestAlgoliaProxyWithEdxPartner, cls).setUpClass()
        Partner.objects.all().delete()
        Site.objects.all().delete()
        cls.site = SiteFactory(id=settings.SITE_ID, domain=TEST_DOMAIN)
        cls.edxPartner = PartnerFactory(site=cls.site)
        cls.edxPartner.name = 'edX'


@pytest.mark.django_db
class TestAlgoliaProxyCourse(TestAlgoliaProxyWithEdxPartner):

    def test_should_index(self):
        course = AlgoliaProxyCourseFactory(partner=self.__class__.edxPartner)
        course.authoring_organizations.add(OrganizationFactory())
        assert course.should_index()

    def test_do_not_index_if_no_owners(self):
        course = AlgoliaProxyCourseFactory(partner=self.__class__.edxPartner)
        assert not course.should_index()

    def test_do_not_index_if_owner_missing_logo(self):
        course = AlgoliaProxyCourseFactory(partner=self.__class__.edxPartner)
        course.authoring_organizations.add(OrganizationFactory(logo_image=None))
        assert not course.should_index()

    def test_do_not_index_if_no_url_slug(self):
        course = AlgoliaProxyCourseFactory(partner=self.__class__.edxPartner)
        course.authoring_organizations.add(OrganizationFactory())
        for url_slug in course.url_slug_history.all():
            url_slug.is_active = False
            url_slug.save()
        assert not course.should_index()

    def test_do_not_index_if_partner_not_edx(self):
        course = AlgoliaProxyCourseFactory(partner=PartnerFactory())
        course.authoring_organizations.add(OrganizationFactory())
        assert not course.should_index()


@pytest.mark.django_db
class TestAlgoliaProxyProgram(TestAlgoliaProxyWithEdxPartner):

    def test_should_index(self):
        program = AlgoliaProxyProgramFactory(partner=self.__class__.edxPartner)
        program.authoring_organizations.add(OrganizationFactory())
        assert program.should_index()

    def test_do_not_index_if_no_owners(self):
        program = AlgoliaProxyProgramFactory(partner=self.__class__.edxPartner)
        assert not program.should_index()

    def test_do_not_index_if_owner_missing_logo(self):
        program = AlgoliaProxyProgramFactory(partner=self.__class__.edxPartner)
        program.authoring_organizations.add(OrganizationFactory(logo_image=None))
        assert not program.should_index()

    def test_do_not_index_if_partner_not_edx(self):
        program = AlgoliaProxyProgramFactory(partner=PartnerFactory())
        program.authoring_organizations.add(OrganizationFactory())
        assert not program.should_index()
