# pylint: disable=redefined-builtin,no-member
import datetime
import xml.etree.ElementTree as ET
from os.path import abspath, dirname, join

import ddt
import pytz
from lxml import etree
from rest_framework.reverse import reverse
from rest_framework.test import APITestCase

from course_discovery.apps.api.serializers import AffiliateWindowSerializer
from course_discovery.apps.api.v1.tests.test_views.mixins import SerializationMixin
from course_discovery.apps.catalogs.tests.factories import CatalogFactory
from course_discovery.apps.core.tests.factories import UserFactory
from course_discovery.apps.core.tests.mixins import ElasticsearchTestMixin
from course_discovery.apps.course_metadata.choices import CourseRunStatus
from course_discovery.apps.course_metadata.models import Seat
from course_discovery.apps.course_metadata.tests.factories import CourseRunFactory, SeatFactory


@ddt.ddt
class AffiliateWindowViewSetTests(ElasticsearchTestMixin, SerializationMixin, APITestCase):
    """ Tests for the AffiliateWindowViewSet. """

    def setUp(self):
        super(AffiliateWindowViewSetTests, self).setUp()
        self.user = UserFactory()
        self.client.force_authenticate(self.user)
        self.catalog = CatalogFactory(query='*:*', viewers=[self.user])

        self.enrollment_end = datetime.datetime.now(pytz.UTC) + datetime.timedelta(days=30)
        self.course_end = datetime.datetime.now(pytz.UTC) + datetime.timedelta(days=60)
        self.course_run = CourseRunFactory(enrollment_end=self.enrollment_end, end=self.course_end)

        self.seat_verified = SeatFactory(course_run=self.course_run, type=Seat.VERIFIED)
        self.course = self.course_run.course
        self.affiliate_url = reverse('api:v1:partners:affiliate_window-detail', kwargs={'pk': self.catalog.id})
        self.refresh_index()

    def test_without_authentication(self):
        """ Verify authentication is required when accessing the endpoint. """
        self.client.logout()
        response = self.client.get(self.affiliate_url)
        self.assertEqual(response.status_code, 403)

    def test_affiliate_with_supported_seats(self):
        """ Verify that endpoint returns course runs for verified and professional seats only. """
        with self.assertNumQueries(8):
            response = self.client.get(self.affiliate_url)

        self.assertEqual(response.status_code, 200)
        root = ET.fromstring(response.content)
        self.assertEqual(1, len(root.findall('product')))
        self.assert_product_xml(
            root.findall('product/[pid="{}-{}"]'.format(self.course_run.key, self.seat_verified.type))[0],
            self.seat_verified
        )

        # Add professional seat.
        seat_professional = SeatFactory(course_run=self.course_run, type=Seat.PROFESSIONAL)

        response = self.client.get(self.affiliate_url)
        root = ET.fromstring(response.content)
        self.assertEqual(2, len(root.findall('product')))

        self.assert_product_xml(
            root.findall('product/[pid="{}-{}"]'.format(self.course_run.key, self.seat_verified.type))[0],
            self.seat_verified
        )
        self.assert_product_xml(
            root.findall('product/[pid="{}-{}"]'.format(self.course_run.key, seat_professional.type))[0],
            seat_professional
        )

    @ddt.data(Seat.CREDIT, Seat.HONOR, Seat.AUDIT)
    def test_with_non_supported_seats(self, non_supporting_seat):
        """ Verify that endpoint returns no data for honor, credit and audit seats. """

        self.seat_verified.type = non_supporting_seat
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
        self.assertEqual(content.find('pid').text, '{}-{}'.format(self.course_run.key, seat.type))
        self.assertEqual(content.find('name').text, self.course_run.title)
        self.assertEqual(content.find('desc').text, self.course_run.short_description)
        self.assertEqual(content.find('purl').text, self.course_run.marketing_url)
        self.assertEqual(content.find('imgurl').text, self.course_run.card_image_url)
        self.assertEqual(content.find('price/actualp').text, str(seat.price))
        self.assertEqual(content.find('currency').text, seat.currency.code)
        self.assertEqual(content.find('category').text, AffiliateWindowSerializer.CATEGORY)

    def test_dtd_with_valid_data(self):
        """ Verify the XML data produced by the endpoint conforms to the DTD file. """
        response = self.client.get(self.affiliate_url)
        self.assertEqual(response.status_code, 200)
        filename = abspath(join(dirname(dirname(__file__)), 'affiliate_window_product_feed.1.4.dtd'))
        dtd = etree.DTD(open(filename))

        root = etree.XML(response.content)
        self.assertTrue(dtd.validate(root))

    def test_permissions(self):
        """ Verify only users with the appropriate permissions can access the endpoint. """
        catalog = CatalogFactory()
        superuser = UserFactory(is_superuser=True)
        url = reverse('api:v1:partners:affiliate_window-detail', kwargs={'pk': catalog.id})

        # Superusers can view all catalogs
        self.client.force_authenticate(superuser)

        with self.assertNumQueries(4):
            response = self.client.get(url)
            self.assertEqual(response.status_code, 200)

        # Regular users can only view catalogs belonging to them
        self.client.force_authenticate(self.user)
        response = self.client.get(url)
        self.assertEqual(response.status_code, 403)

        catalog.viewers = [self.user]
        with self.assertNumQueries(7):
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
