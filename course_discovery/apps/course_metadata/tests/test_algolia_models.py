import datetime
from collections import ChainMap

import pytest
from django.conf import settings
from django.contrib.sites.models import Site
from django.test import TestCase, override_settings
from pytz import UTC

from conftest import TEST_DOMAIN
from course_discovery.apps.core.models import Partner
from course_discovery.apps.core.tests.factories import PartnerFactory, SiteFactory
from course_discovery.apps.course_metadata.algolia_proxy_models import AlgoliaProxyCourse, AlgoliaProxyProgram
from course_discovery.apps.course_metadata.models import CourseRunStatus
from course_discovery.apps.course_metadata.tests.factories import (
    CourseFactory, CourseRunFactory, OrganizationFactory, ProgramFactory, SeatFactory, SeatTypeFactory
)


class AlgoliaProxyCourseFactory(CourseFactory):
    class Meta:
        model = AlgoliaProxyCourse


class AlgoliaProxyProgramFactory(ProgramFactory):
    class Meta:
        model = AlgoliaProxyProgram


@override_settings(SETTING_DICT=ChainMap({'AUTO_INDEXING': 'False'}, settings.ALGOLIA))
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

    YESTERDAY = datetime.datetime.now(UTC) - datetime.timedelta(days=1)
    TOMORROW = datetime.datetime.now(UTC) + datetime.timedelta(days=1)
    IN_THREE_DAYS = datetime.datetime.now(UTC) + datetime.timedelta(days=3)
    IN_FIFTEEN_DAYS = datetime.datetime.now(UTC) + datetime.timedelta(days=15)

    def create_current_upgradeable_course(self):
        course = AlgoliaProxyCourseFactory(partner=self.__class__.edxPartner)
        current_upgradeable_course_run = CourseRunFactory(
            course=course,
            start=self.YESTERDAY,
            end=self.IN_FIFTEEN_DAYS,
            enrollment_end=self.IN_FIFTEEN_DAYS,
            status=CourseRunStatus.Published,
        )
        SeatFactory(
            course_run=current_upgradeable_course_run,
            type=SeatTypeFactory.verified(),
            upgrade_deadline=self.TOMORROW,
            price=10
        )
        return course

    def create_upgradeable_course_ending_soon(self):
        course = AlgoliaProxyCourseFactory(partner=self.__class__.edxPartner)
        upgradeable_course_run = CourseRunFactory(
            course=course,
            start=self.YESTERDAY,
            end=self.IN_THREE_DAYS,
            enrollment_end=self.IN_THREE_DAYS,
            status=CourseRunStatus.Published
        )

        SeatFactory(
            course_run=upgradeable_course_run,
            type=SeatTypeFactory.verified(),
            upgrade_deadline=self.TOMORROW,
            price=10
        )
        return course

    def create_upgradeable_course_starting_soon(self):
        course = AlgoliaProxyCourseFactory(partner=self.__class__.edxPartner)
        upgradeable_course_run = CourseRunFactory(
            course=course,
            start=self.TOMORROW,
            end=self.IN_FIFTEEN_DAYS,
            enrollment_end=self.IN_FIFTEEN_DAYS,
            status=CourseRunStatus.Published
        )

        SeatFactory(
            course_run=upgradeable_course_run,
            type=SeatTypeFactory.verified(),
            upgrade_deadline=self.IN_FIFTEEN_DAYS,
            price=10
        )
        return course

    def create_current_non_upgradeable_course(self):
        course = AlgoliaProxyCourseFactory(partner=self.__class__.edxPartner)

        non_upgradeable_course_run = CourseRunFactory(
            course=course,
            start=self.YESTERDAY,
            end=self.IN_FIFTEEN_DAYS,
            enrollment_end=self.IN_FIFTEEN_DAYS,
            status=CourseRunStatus.Published
        )
        # not upgradeable because upgrade_deadline has passed
        SeatFactory(
            course_run=non_upgradeable_course_run,
            type=SeatTypeFactory.verified(),
            upgrade_deadline=self.YESTERDAY,
            price=10
        )
        return course

    def create_upcoming_non_upgradeable_course(self, additional_days=0):
        course = AlgoliaProxyCourseFactory(partner=self.__class__.edxPartner)
        future_course_run = CourseRunFactory(
            course=course,
            start=self.IN_THREE_DAYS + datetime.timedelta(days=additional_days),
            end=self.IN_FIFTEEN_DAYS + datetime.timedelta(days=additional_days),
            enrollment_end=self.IN_THREE_DAYS + datetime.timedelta(days=additional_days),
            status=CourseRunStatus.Published
        )
        SeatFactory(
            course_run=future_course_run,
            type=SeatTypeFactory.verified(),
            upgrade_deadline=self.YESTERDAY,
            price=10
        )
        return course

    def create_course_with_basic_active_course_run(self):
        course = AlgoliaProxyCourseFactory(partner=self.__class__.edxPartner)

        course_run = CourseRunFactory(
            course=course,
            start=self.YESTERDAY,
            end=self.YESTERDAY,
            status=CourseRunStatus.Published
        )
        SeatFactory(
            course_run=course_run,
            type=SeatTypeFactory.audit(),
        )
        return course

    def test_should_index(self):
        course = self.create_course_with_basic_active_course_run()
        course.authoring_organizations.add(OrganizationFactory())
        assert course.should_index()

    def test_do_not_index_if_no_owners(self):
        course = self.create_course_with_basic_active_course_run()
        assert not course.should_index()

    def test_do_not_index_if_owner_missing_logo(self):
        course = self.create_course_with_basic_active_course_run()
        course.authoring_organizations.add(OrganizationFactory(logo_image=None))
        assert not course.should_index()

    def test_do_not_index_if_no_url_slug(self):
        course = self.create_course_with_basic_active_course_run()
        course.authoring_organizations.add(OrganizationFactory())
        for url_slug in course.url_slug_history.all():
            url_slug.is_active = False
            url_slug.save()
        assert not course.should_index()

    def test_do_not_index_if_partner_not_edx(self):
        course = self.create_course_with_basic_active_course_run()
        course.partner = PartnerFactory()
        course.authoring_organizations.add(OrganizationFactory())
        assert not course.should_index()

    def test_do_not_index_if_no_active_course_run(self):
        course = AlgoliaProxyCourseFactory(partner=self.__class__.edxPartner)
        course.authoring_organizations.add(OrganizationFactory())
        assert not course.should_index()

    def test_current_and_upgradeable_beats_just_upgradeable(self):
        course_1 = self.create_current_upgradeable_course()
        course_2 = self.create_upgradeable_course_ending_soon()
        course_3 = self.create_upgradeable_course_starting_soon()
        assert course_1.availability_rank() < course_2.availability_rank()
        assert course_1.availability_rank() < course_3.availability_rank()
        assert course_2.availability_rank() == course_3.availability_rank()

    def test_upgradeable_beats_just_current(self):
        course_1 = self.create_upgradeable_course_ending_soon()
        course_2 = self.create_current_non_upgradeable_course()
        assert course_1.availability_rank() < course_2.availability_rank()

    def test_current_non_upgradeable_beats_upcoming_non_upgradeable(self):
        course_1 = self.create_current_non_upgradeable_course()
        course_2 = self.create_upcoming_non_upgradeable_course()
        assert course_1.availability_rank() < course_2.availability_rank()

    def test_earliest_upcoming_wins(self):
        course_1 = self.create_upcoming_non_upgradeable_course()
        course_2 = self.create_upcoming_non_upgradeable_course(additional_days=1)
        assert course_1.availability_rank() < course_2.availability_rank()

    def test_active_course_run_beats_no_active_course_run(self):
        course_1 = self.create_course_with_basic_active_course_run()
        course_2 = AlgoliaProxyCourseFactory(partner=self.__class__.edxPartner)
        CourseRunFactory(
            course=course_2,
            start=self.YESTERDAY,
            end=self.YESTERDAY,
            enrollment_end=self.YESTERDAY,
            status=CourseRunStatus.Published
        )
        assert course_1.availability_rank()
        assert not course_2.availability_rank()


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
