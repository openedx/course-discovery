"""
Helper methods for testing the processing of image files.
"""
from io import BytesIO
from PIL import Image

from django.core.files.uploadedfile import SimpleUploadedFile


def make_image_stream(width, height):
    """
    Helper to generate values for program banner_image
    """
    image = Image.new('RGB', (width, height), 'green')
    bio = BytesIO()
    image.save(bio, format='JPEG')
    return bio


def make_image_file(name, width=2120, height=1192):
    image_stream = make_image_stream(width, height)
    return SimpleUploadedFile(name, image_stream.getvalue(), content_type='image/jpeg')
