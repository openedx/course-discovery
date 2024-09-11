import csv
import datetime
import logging

from django.conf import settings
from django.core.management import BaseCommand, CommandError
from django.db.models import Count, Prefetch, Q

from course_discovery.apps.course_metadata.gspread_client import GspreadClient
from course_discovery.apps.course_metadata.models import Course, CourseType, Program, SubjectTranslation

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = """
    Populates Product Catalog for Salesforce Marketing Cloud Catalog

    Example usage:
    python manage.py populate_product_catalog --product_type={product_type} --output_csv=/path/to/output.csv --product_source={product_source}
    python manage.py populate_product_catalog --product_type={product_type} --product_source={product_source} --use_gspread_client=True --overwrite=True
    """

    CATALOG_CSV_HEADERS = [
        'UUID', 'Title', 'Organizations Name', 'Organizations Logo', 'Organizations Abbr', 'Languages',
        'Subjects', 'Subjects Spanish', 'Marketing URL', 'Marketing Image'
    ]

    def add_arguments(self, parser):
        parser.add_argument(
            '--product_type',
            dest='product_type',
            type=str,
            required=False,
            help='Product Type to populate in the catalog'
        )
        parser.add_argument(
            '--output_csv',
            dest='output_csv',
            type=str,
            required=False,
            help='Path of the output CSV'
        )
        parser.add_argument(
            '--product_source',
            dest='product_source',
            type=str,
            required=False,
            help='The product source to filter the products'
        )
        parser.add_argument(
            '--use_gspread_client',
            dest='gspread_client_flag',
            type=bool,
            required=False,
            help='Flag to use Gspread Client for writing data to Google Sheets'
        )
        parser.add_argument(
            '--overwrite',
            dest='overwrite_flag',
            type=bool,
            default=True,
            required=False,
            help='Flag to overwrite the existing data in Google Sheet tab'
        )

    def get_products(self, product_type, product_source):
        """
        Extract products from the DB for product catalog
        """
        ocm_course_catalog_types = [
            CourseType.AUDIT, CourseType.VERIFIED_AUDIT, CourseType.PROFESSIONAL, CourseType.CREDIT_VERIFIED_AUDIT,
            'verified', 'spoc-verified-audit'
        ]

        if product_type in ['executive_education', 'bootcamp', 'ocm_course']:
            queryset = Course.objects.available(exclude_hidden_runs=True).select_related('partner', 'type')

            if product_type == 'ocm_course':
                queryset = queryset.filter(type__slug__in=ocm_course_catalog_types)

            elif product_type == 'executive_education':
                queryset = queryset.filter(type__slug=CourseType.EXECUTIVE_EDUCATION_2U)

            elif product_type == 'bootcamp':
                queryset = queryset.filter(type__slug=CourseType.BOOTCAMP_2U)

            if product_source:
                queryset = queryset.filter(product_source__slug=product_source)

            queryset = queryset.annotate(
                num_orgs=Count('authoring_organizations')
            ).filter(Q(num_orgs__gt=0) & Q(image__isnull=False) & ~Q(image=''))

            # Prefetch Spanish translations of subjects
            subject_translations = Prefetch(
                'subjects__translations',
                queryset=SubjectTranslation.objects.filter(language_code='es'),
                to_attr='spanish_translations'
            )

            return queryset.prefetch_related(
                'authoring_organizations',
                'subjects',
                subject_translations
            )
        elif product_type == 'degree':
            queryset = Program.objects.marketable().exclude(degree__isnull=True).select_related('partner', 'type')

            if product_source:
                queryset = queryset.filter(product_source__slug=product_source)

            queryset = queryset.annotate(
                num_orgs=Count('authoring_organizations')
            ).filter(Q(num_orgs__gt=0) & Q(card_image__isnull=False) & ~Q(card_image=''))

            subject_translations = Prefetch(
                'courses__subjects__translations',
                queryset=SubjectTranslation.objects.filter(language_code='es'),
                to_attr='spanish_translations'
            )

            return queryset.prefetch_related(
                'authoring_organizations',
                'courses__subjects',
                'courses__course_runs',
                subject_translations,
            )
        else:
            # Return empty queryset if invalid product type specified
            return Course.objects.none()

    def write_csv_header(self, output_csv):
        """
        Write the header of output CSV in the file.
        """
        writer = csv.DictWriter(output_csv, fieldnames=self.CATALOG_CSV_HEADERS)
        writer.writeheader()
        return writer

    def get_transformed_data(self, product, product_type):
        """
        Transforms the product data for product's catalog
        """
        authoring_orgs = product.authoring_organizations.all()

        data = {
            "UUID": str(product.uuid.hex),
            "Title": product.title,
            "Organizations Name": ", ".join(org.name for org in authoring_orgs),
            "Organizations Logo": ", ".join(org.logo_image.url for org in authoring_orgs if org.logo_image),
            "Organizations Abbr": ", ".join(org.key for org in authoring_orgs),
            "Marketing URL": product.marketing_url,
        }
        if product_type in ['executive_education', 'bootcamp', 'ocm_course']:
            data.update({
                "Subjects": ", ".join(subject.name for subject in product.subjects.all()),
                "Subjects Spanish": ", ".join(
                    translation.name for subject in product.subjects.all()
                    for translation in subject.spanish_translations
                ),
                "Languages": product.languages_codes(),
                "Marketing Image": product.image.url if product.image else "",
            })
        elif product_type == 'degree':
            data.update({
                "Subjects": ", ".join(subject.name for subject in product.subjects),
                "Subjects Spanish": ", ".join(
                    translation.name for subject in product.subjects
                    for translation in subject.spanish_translations
                ),
                "Languages": ", ".join(language.code for language in product.languages),
                "Marketing Image": product.card_image.url if product.card_image else "",
            })

        return data

    def handle(self, *args, **options):
        product_type = options.get('product_type')
        output_csv = options.get('output_csv')
        product_source = options.get('product_source')
        gspread_client_flag = options.get('gspread_client_flag')
        overwrite = options.get('overwrite_flag')
        PRODUCT_CATALOG_CONFIG = {
            'SHEET_ID': settings.PRODUCT_CATALOG_SHEET_ID,
            'OUTPUT_TAB_ID': (
                product_type.upper() + ('_' + datetime.datetime.now().strftime("%Y%m%d") if not overwrite else '')
                if product_type else 'All'
            ),
        }

        gspread_client = GspreadClient()

        try:
            product_type = product_type.lower()
            products = self.get_products(product_type, product_source)
            if not products.exists():
                raise CommandError('No products found for the given criteria.')
            products_count = products.count()

            logger.info(f'Fetched {products_count} courses from the database')
            if output_csv:
                with open(output_csv, 'w', newline='') as output_file:
                    output_writer = self.write_csv_header(output_file)
                    for product in products:
                        try:
                            output_writer.writerow(self.get_transformed_data(product, product_type))
                        except Exception as e:  # pylint: disable=broad-exception-caught
                            logger.error(f"Error writing product {product.uuid} to CSV: {str(e)}")
                            continue

                    logger.info(f'Populated {products_count} {product_type}s to {output_csv}')

            elif gspread_client_flag:
                csv_data = [self.get_transformed_data(product, product_type) for product in products]
                gspread_client.write_data(
                    PRODUCT_CATALOG_CONFIG,
                    self.CATALOG_CSV_HEADERS,
                    csv_data,
                    overwrite=overwrite,
                )
                logger.info(f'Populated {products_count} {product_type}s to Google Sheets')

        except Exception as e:
            raise CommandError(f'Error while populating product catalog: {str(e)}') from e
