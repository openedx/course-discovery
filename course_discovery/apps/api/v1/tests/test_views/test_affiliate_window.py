import datetime
import xml.etree.ElementTree as ET
from os.path import abspath, dirname, join

import ddt
import pytz
from lxml import etree
from rest_framework import status
from rest_framework.reverse import reverse

from course_discovery.apps.api.serializers import AffiliateWindowSerializer, ProgramsAffiliateWindowSerializer
from course_discovery.apps.api.v1.tests.test_views.mixins import APITestCase, SerializationMixin
from course_discovery.apps.catalogs.tests.factories import CatalogFactory
from course_discovery.apps.core.tests.factories import UserFactory
from course_discovery.apps.core.tests.helpers import make_image_file
from course_discovery.apps.core.tests.mixins import ElasticsearchTestMixin
from course_discovery.apps.course_metadata.choices import CourseRunStatus
from course_discovery.apps.course_metadata.models import ProgramType, Seat, SeatType
from course_discovery.apps.course_metadata.tests.factories import (
    CourseRunFactory, ProgramFactory, SeatFactory, SeatTypeFactory
)


@ddt.ddt
class ProgramsAffiliateWindowViewSetTests(SerializationMixin, APITestCase):
    """ Tests for the ProgramsAffiliateWindowViewSet. """
    def _assert_product_xml(self, content, program):
        """ Helper method to verify product data in xml format. """
        assert content.find('pid').text == f'{program.uuid}'
        assert content.find('name').text == program.title
        assert content.find('desc').text == program.overview
        assert content.find('purl').text == program.marketing_url
        assert content.find('imgurl').text == program.banner_image.url
        assert content.find('category').text == ProgramsAffiliateWindowSerializer.CATEGORY

    def setUp(self):
        super().setUp()
        self.user = UserFactory()
        self.client.force_authenticate(self.user)
        self.catalog = CatalogFactory(query='*:*', program_query='*:*', viewers=[self.user])

        self.enrollment_end = datetime.datetime.now(pytz.UTC) + datetime.timedelta(days=30)
        self.course_end = datetime.datetime.now(pytz.UTC) + datetime.timedelta(days=60)
        self.course_run = CourseRunFactory(enrollment_end=self.enrollment_end, end=self.course_end)
        self.course = self.course_run.course

        # Generate test programs
        self.test_image = make_image_file('test_banner.jpg')
        self.masters_program_type = ProgramType.objects.get(slug=ProgramType.MASTERS)
        self.microbachelors_program_type = ProgramType.objects.get(slug=ProgramType.MICROBACHELORS)
        self.ms_program = ProgramFactory(
            type=self.masters_program_type,
            courses=[self.course],
            banner_image=self.test_image,
        )
        self.program = ProgramFactory(
            type=self.microbachelors_program_type,
            courses=[self.course],
            banner_image=self.test_image,
        )

        self.affiliate_url = reverse('api:v1:partners:programs_affiliate_window-detail', kwargs={'pk': self.catalog.id})

    def test_without_authentication(self):
        """ Verify authentication is required when accessing the endpoint. """
        self.client.logout()
        response = self.client.get(self.affiliate_url)
        self.assertEqual(response.status_code, 401)

    def test_affiliate_with_approved_programs(self):
        """Verify that only the expected Program types are returned, No Masters programs"""
        response = self.client.get(self.affiliate_url)
        assert response.status_code == status.HTTP_200_OK
        root = ET.fromstring(response.content)

        # Assert that there is only on Program in the returned data even though 2
        # are created in setup
        assert len(root.findall('product')) == 1
        self._assert_product_xml(
            root.findall(f'product/[pid="{self.program.uuid}"]')[0],
            self.program
        )

        # Add a new program of approved type and verify it is available
        mm_program_type = ProgramType.objects.get(slug=ProgramType.MICROMASTERS)
        mm_program = ProgramFactory(type=mm_program_type, courses=[self.course], banner_image=self.test_image)

        response = self.client.get(self.affiliate_url)
        assert response.status_code == status.HTTP_200_OK
        root = ET.fromstring(response.content)

        # Assert that there is only on Program in the returned data even though 2
        # are created in setup
        assert len(root.findall('product')) == 2
        self._assert_product_xml(
            root.findall(f'product/[pid="{self.program.uuid}"]')[0],
            self.program
        )

        self._assert_product_xml(
            root.findall(f'product/[pid="{mm_program.uuid}"]')[0],
            mm_program
        )

        # Verify that the Masters program is not in the data
        assert not root.findall(f'product/[pid="{self.ms_program.uuid}"]')


@ddt.ddt
class AffiliateWindowViewSetTests(ElasticsearchTestMixin, SerializationMixin, APITestCase):
    """ Tests for the AffiliateWindowViewSet. """

    def setUp(self):
        super().setUp()
        self.user = UserFactory()
        self.client.force_authenticate(self.user)
        self.catalog = CatalogFactory(query='*:*', viewers=[self.user])

        self.enrollment_end = datetime.datetime.now(pytz.UTC) + datetime.timedelta(days=30)
        self.course_end = datetime.datetime.now(pytz.UTC) + datetime.timedelta(days=60)
        self.course_run = CourseRunFactory(enrollment_end=self.enrollment_end, end=self.course_end)

        self.seat_verified = SeatFactory(course_run=self.course_run, type=SeatTypeFactory.verified())
        self.course = self.course_run.course
        self.affiliate_url = reverse('api:v1:partners:affiliate_window-detail', kwargs={'pk': self.catalog.id})
        self.refresh_index()

    def test_without_authentication(self):
        """ Verify authentication is required when accessing the endpoint. """
        self.client.logout()
        response = self.client.get(self.affiliate_url)
        self.assertEqual(response.status_code, 401)

    def test_affiliate_with_supported_seats(self):
        """ Verify that endpoint returns course runs for verified and professional seats only. """
        response = self.client.get(self.affiliate_url)

        self.assertEqual(response.status_code, 200)
        root = ET.fromstring(response.content)
        self.assertEqual(1, len(root.findall('product')))
        self.assert_product_xml(
            root.findall(f'product/[pid="{self.course_run.key}-{self.seat_verified.type.slug}"]')[0],
            self.seat_verified
        )

        # Add professional seat
        seat_professional = SeatFactory(course_run=self.course_run, type=SeatTypeFactory.professional())

        response = self.client.get(self.affiliate_url)
        root = ET.fromstring(response.content)
        self.assertEqual(2, len(root.findall('product')))

        self.assert_product_xml(
            root.findall(f'product/[pid="{self.course_run.key}-{self.seat_verified.type.slug}"]')[0],
            self.seat_verified
        )
        self.assert_product_xml(
            root.findall(f'product/[pid="{self.course_run.key}-{seat_professional.type.slug}"]')[0],
            seat_professional
        )

    @ddt.data(Seat.CREDIT, Seat.HONOR, Seat.AUDIT)
    def test_with_non_supported_seats(self, non_supporting_seat):
        """ Verify that endpoint returns no data for honor, credit and audit seats. """

        self.seat_verified.type = SeatType.objects.get_or_create(slug=non_supporting_seat)[0]
        self.seat_verified.save()

        response = self.client.get(self.affiliate_url)
        self.assertEqual(response.status_code, 200)
        root = ET.fromstring(response.content)
        self.assertEqual(0, len(root.findall('product')))

    def test_with_closed_enrollment(self):
        """ Verify that endpoint returns no data if enrollment is close. """
        self.course_run.enrollment_end = datetime.datetime.now(pytz.UTC) - datetime.timedelta(days=100)
        self.course_run.end = datetime.datetime.now(pytz.UTC) - datetime.timedelta(days=100)
        self.course_run.save()

        # new course run with future end date and no enrollment_date.
        CourseRunFactory(end=self.course_end, course=self.course, enrollment_end=None)

        response = self.client.get(self.affiliate_url)

        self.assertEqual(response.status_code, 200)
        root = ET.fromstring(response.content)
        self.assertEqual(0, len(root.findall('product')))

    def assert_product_xml(self, content, seat):
        """ Helper method to verify product data in xml format. """
        assert content.find('pid').text == f'{self.course_run.key}-{seat.type.slug}'
        assert content.find('name').text == self.course_run.title
        assert content.find('desc').text == self.course_run.full_description
        assert content.find('purl').text == self.course_run.marketing_url
        assert content.find('imgurl').text == self.course_run.image_url
        assert content.find('price/actualp').text == str(seat.price)
        assert content.find('currency').text == seat.currency.code
        assert content.find('category').text == AffiliateWindowSerializer.CATEGORY

    def test_dtd_with_valid_data(self):
        """ Verify the XML data produced by the endpoint conforms to the DTD file. """
        response = self.client.get(self.affiliate_url)
        assert response.status_code == 200

        filename = abspath(join(dirname(dirname(__file__)), 'affiliate_window_product_feed.1.4.dtd'))
        dtd = etree.DTD(open(filename))
        root = etree.XML(response.content)
        assert dtd.validate(root)

    def test_permissions(self):
        """ Verify only users with the appropriate permissions can access the endpoint. """
        catalog = CatalogFactory()
        superuser = UserFactory(is_superuser=True)
        url = reverse('api:v1:partners:affiliate_window-detail', kwargs={'pk': catalog.id})

        # Superusers can view all catalogs
        self.client.force_authenticate(superuser)

        with self.assertNumQueries(6, threshold=1):  # CI is often 7
            response = self.client.get(url)
            self.assertEqual(response.status_code, 200)

        # Regular users can only view catalogs belonging to them
        self.client.force_authenticate(self.user)
        response = self.client.get(url)
        self.assertEqual(response.status_code, 403)

        catalog.viewers = [self.user]
        with self.assertNumQueries(9, threshold=1):  # CI is often 10
            response = self.client.get(url)
            self.assertEqual(response.status_code, 200)

    def test_unpublished_status(self):
        """ Verify the endpoint does not return CourseRuns in a non-published state. """
        self.course_run.status = CourseRunStatus.Unpublished
        self.course_run.save()

        CourseRunFactory(course=self.course, status=CourseRunStatus.Unpublished)

        response = self.client.get(self.affiliate_url)

        self.assertEqual(response.status_code, 200)
        root = ET.fromstring(response.content)
        self.assertEqual(0, len(root.findall('product')))
