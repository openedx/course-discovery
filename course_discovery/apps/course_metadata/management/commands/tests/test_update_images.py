from unittest import mock

from django.core.management import call_command
from django.test import TestCase

from course_discovery.apps.course_metadata.models import BulkUpdateImagesConfig
from course_discovery.apps.course_metadata.tests.factories import ImageFactory


class UpdateImagesCommandTest(TestCase):
    LOGGER_PATH = 'course_discovery.apps.course_metadata.management.commands.update_images.logger'

    def setUp(self):
        super().setUp()
        self.config = BulkUpdateImagesConfig.get_solo()

    def testNormalRun(self):
        image0 = ImageFactory()
        image1 = ImageFactory()
        self.config.image_urls = '''{src0} https://www.edx.org/bananas-in-pajamas.jpg
        {src1} http://www.edx.org/are_coming_down_the_stairs.jpg'''.format(src0=image0.src, src1=image1.src)
        self.config.save()
        call_command('update_images')
        image0.refresh_from_db()
        image1.refresh_from_db()
        assert image0.src == 'https://www.edx.org/bananas-in-pajamas.jpg'
        assert image1.src == 'http://www.edx.org/are_coming_down_the_stairs.jpg'

    @mock.patch(LOGGER_PATH)
    def testBadUrl(self, mock_logger):
        image = ImageFactory()
        initial_src = image.src
        self.config.image_urls = '{src} not-a-url'.format(src=image.src)
        self.config.save()
        call_command('update_images')
        mock_logger.warning.assert_called_with('Invalid image url: "not-a-url"')
        image.refresh_from_db()
        assert image.src == initial_src

    @mock.patch(LOGGER_PATH)
    def testImageDoesntExist(self, mock_logger):
        self.config.image_urls = 'https://doesnt-exist.com/image.jpg http://www.edx.org/fine.jpg'
        self.config.save()
        call_command('update_images')
        mock_logger.warning.assert_called_with('Cannot find image with url "https://doesnt-exist.com/image.jpg"')

    @mock.patch(LOGGER_PATH)
    def testUnreadableLine(self, mock_logger):
        self.config.image_urls = 'NopeNopeNope'
        self.config.save()
        call_command('update_images')
        mock_logger.warning.assert_called_with('Incorrectly formatted line %s', 'NopeNopeNope')
