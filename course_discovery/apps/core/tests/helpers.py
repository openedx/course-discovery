"""
Helper methods for testing the processing of image files.
"""
from io import BytesIO
from PIL import Image

from django.core.files.uploadedfile import SimpleUploadedFile


def make_image_stream():
    """
    Helper to generate values for program banner_image
    """
    image = Image.new('RGB', (1440, 900), 'green')
    bio = BytesIO()
    image.save(bio, format='JPEG')
    return bio


def make_image_file(name):
    image_stream = make_image_stream()
    return SimpleUploadedFile(name, image_stream.getvalue(), content_type='image/jpeg')
