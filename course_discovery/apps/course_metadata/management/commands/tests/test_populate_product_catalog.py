"""
Unit tests for populate_product_catalog management command.
"""
import csv
from tempfile import NamedTemporaryFile

import mock
from django.core.management import CommandError, call_command
from django.test import TestCase

from course_discovery.apps.course_metadata.choices import CourseRunStatus
from course_discovery.apps.course_metadata.management.commands.populate_product_catalog import Command
from course_discovery.apps.course_metadata.models import Course, CourseType
from course_discovery.apps.course_metadata.tests.factories import (
    CourseFactory, CourseRunFactory, CourseTypeFactory, PartnerFactory, SeatFactory, SourceFactory
)


class PopulateProductCatalogCommandTests(TestCase):
    def setUp(self):
        super().setUp()
        self.partner = PartnerFactory.create()
        self.course_type = CourseTypeFactory(slug=CourseType.AUDIT)
        self.source = SourceFactory.create(slug="edx")
        self.courses = CourseFactory.create_batch(
            2,
            product_source=self.source,
            partner=self.partner,
            additional_metadata=None,
            type=self.course_type,
        )
        self.course_run = CourseRunFactory(
            course=Course.objects.all()[0],
            status=CourseRunStatus.Published,
        )
        self.seat = SeatFactory.create(course_run=self.course_run)
        self.course_run_2 = CourseRunFactory.create_batch(
            2, course=Course.objects.all()[1]
        )

    def test_populate_product_catalog(self):
        """
        Test populate_product_catalog command and verify data has been populated successfully
        """
        with NamedTemporaryFile(mode="w", delete=False) as output_csv:
            call_command(
                "populate_product_catalog",
                product_type="ocm_course",
                output_csv=output_csv.name,
                product_source="edx",
                gspread_client_flag=False,
            )

        with open(output_csv.name, "r") as output_csv_file:
            csv_reader = csv.DictReader(output_csv_file)
            for row in csv_reader:
                self.assertIn("UUID", row)
                self.assertIn("Title", row)
                self.assertIn("Organizations Name", row)
                self.assertIn("Organizations Logo", row)
                self.assertIn("Organizations Abbr", row)
                self.assertIn("Languages", row)
                self.assertIn("Subjects", row)
                self.assertIn("Subjects Spanish", row)
                self.assertIn("Marketing URL", row)
                self.assertIn("Marketing Image", row)

    @mock.patch(
        "course_discovery.apps.course_metadata.management.commands.populate_product_catalog.Command.get_products"
    )
    def test_get_products_with_product_type(self, mock_get_products):
        """
        Test that the get_products method is called correctly when a specific product type is provided.
        """
        command = Command()
        command.get_products("executive_education", None)

        mock_get_products.assert_called_once_with("executive_education", None)

    def test_handle_no_products_found(self):
        """
        Test to ensure CommandError is raised when no products are found.
        """
        with self.assertRaises(CommandError) as cm:
            call_command("populate_product_catalog", product_type="bootcamp")

        self.assertEqual(
            str(cm.exception),
            "Error while populating product catalog: No products found for the given criteria.",
        )

    @mock.patch(
        "course_discovery.apps.course_metadata.management.commands.populate_product_catalog.csv.DictWriter"
    )
    def test_write_csv_header(self, mock_dict_writer):
        """
        Test that the CSV header is written correctly.
        """
        mock_output_file = mock.Mock()

        command = Command()
        writer = command.write_csv_header(mock_output_file)

        mock_dict_writer.assert_called_once_with(
            mock_output_file, fieldnames=command.CATALOG_CSV_HEADERS
        )
        # pylint: disable=no-member
        writer.writeheader.assert_called_once()

    def test_get_transformed_data(self):
        """
        Verify get_transformed_data method is working correctly
        """
        product = self.courses[0]
        command = Command()
        product_authoring_orgs = product.authoring_organizations.all()
        transformed_prod_data = command.get_transformed_data(product)
        assert transformed_prod_data == {
            "UUID": str(product.uuid),
            "Title": product.title,
            "Organizations Name": ", ".join(
                org.name for org in product_authoring_orgs
            ),
            "Organizations Logo": ", ".join(
                org.logo_image.url
                for org in product_authoring_orgs
                if org.logo_image
            ),
            "Organizations Abbr": ", ".join(
                org.key for org in product_authoring_orgs
            ),
            "Languages": product.languages_codes,
            "Subjects": ", ".join(subject.name for subject in product.subjects.all()),
            "Subjects Spanish": ", ".join(
                translation.name
                for subject in product.subjects.all()
                for translation in subject.spanish_translations
            ),
            "Marketing URL": product.marketing_url,
            "Marketing Image": (product.image.url if product.image else ""),
        }

    @mock.patch('course_discovery.apps.course_metadata.management.commands.populate_product_catalog.GspreadClient')
    @mock.patch(
        'course_discovery.apps.course_metadata.management.commands.populate_product_catalog.Command.get_products'
    )
    def test_handle_gspread_client(self, mock_get_products, mock_gspread_client):
        """
        Ensure GspreadClient is used to write product data when the flag is set.
        """
        mock_get_products.return_value.exists.return_value = True
        mock_get_products.return_value.count.return_value = 1
        mock_get_products.return_value.__iter__.return_value = [mock.MagicMock()]

        mock_client_instance = mock_gspread_client.return_value
        mock_client_instance.write_data.return_value = None

        call_command('populate_product_catalog', product_type='ocm_course', use_gspread_client=True)

        mock_gspread_client.assert_called_once()
        mock_client_instance.write_data.assert_called()
