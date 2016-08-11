"""
Helper methods for testing the processing of image files.

TODO:
    this module was copied (mostly) verbatim from
    edx-platform/master/openedx/core/djangoapps/profile_images/tests/helpers.py
    and could ultimately be moved (with related modules) into a shared utility package.
"""
from io import BytesIO
from django.core.files.uploadedfile import SimpleUploadedFile
from PIL import Image


def make_banner_image_file(name):
    """
    Helper to generate values for program banner_image
    """
    image = Image.new('RGB', (1440, 900), 'green')
    bio = BytesIO()
    image.save(bio, format='JPEG')
    return SimpleUploadedFile(name, bio.getvalue(), content_type='image/jpeg')
