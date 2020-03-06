import pytest
from django.test import TestCase

from course_discovery.apps.api.tests.mixins import SiteMixin
from course_discovery.apps.core.tests.factories import PartnerFactory
from course_discovery.apps.course_metadata.algolia_proxy_models import AlgoliaProxyCourse, AlgoliaProxyProgram
from course_discovery.apps.course_metadata.tests.factories import CourseFactory, OrganizationFactory, ProgramFactory


class AlgoliaProxyCourseFactory(CourseFactory):
    class Meta:
        model = AlgoliaProxyCourse


class AlgoliaProxyProgramFactory(ProgramFactory):
    class Meta:
        model = AlgoliaProxyProgram


@pytest.mark.django_db
class TestAlgoliaProxyCourse(SiteMixin, TestCase):

    def test_should_index(self):
        course = AlgoliaProxyCourseFactory(partner=self.__class__.partner)
        course.authoring_organizations.add(OrganizationFactory())
        assert course.should_index()

    def test_do_not_index_if_no_owners(self):
        course = AlgoliaProxyCourseFactory(partner=self.__class__.partner)
        assert not course.should_index()

    def test_do_not_index_if_owner_missing_logo(self):
        course = AlgoliaProxyCourseFactory(partner=self.__class__.partner)
        course.authoring_organizations.add(OrganizationFactory(logo_image=None))
        assert not course.should_index()

    def test_do_not_index_if_no_url_slug(self):
        course = AlgoliaProxyCourseFactory(partner=self.__class__.partner)
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
class TestAlgoliaProxyProgram(SiteMixin, TestCase):

    def test_should_index(self):
        program = AlgoliaProxyProgramFactory(partner=self.__class__.partner)
        program.authoring_organizations.add(OrganizationFactory())
        assert program.should_index()

    def test_do_not_index_if_no_owners(self):
        program = AlgoliaProxyProgramFactory(partner=self.__class__.partner)
        assert not program.should_index()

    def test_do_not_index_if_owner_missing_logo(self):
        program = AlgoliaProxyProgramFactory(partner=self.__class__.partner)
        program.authoring_organizations.add(OrganizationFactory(logo_image=None))
        assert not program.should_index()

    def test_do_not_index_if_partner_not_edx(self):
        program = AlgoliaProxyProgramFactory(partner=PartnerFactory())
        program.authoring_organizations.add(OrganizationFactory())
        assert not program.should_index()
