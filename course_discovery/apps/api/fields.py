import base64

from django.core.files.base import ContentFile
from rest_framework import serializers


class StdImageSerializerField(serializers.ImageField):
    """
    Custom serializer field to render out proper JSON representation of the StdImage field on model
    """
    def to_representation(self, obj):
        serialized = {}
        for size_key in obj.field.variations:
            # Get different sizes specs from the model field
            # Then get the file path from the available files
            sized_file = getattr(obj, size_key, None)
            if sized_file:
                path = sized_file.url
                serialized_image = serialized.setdefault(size_key, {})
                # In case MEDIA_URL does not include scheme+host, ensure that the URLs are absolute and not relative
                serialized_image['url'] = self.context['request'].build_absolute_uri(path)
                serialized_image['width'] = obj.field.variations[size_key]['width']
                serialized_image['height'] = obj.field.variations[size_key]['height']

        return serialized

    def to_internal_value(self, data):
        """ Save base 64 encoded images """
        # SOURCE: http://matthewdaly.co.uk/blog/2015/07/04/handling-images-as-base64-strings-with-django-rest-framework/
        if not data:
            return None

        if isinstance(data, str) and data.startswith('data:image'):
            # base64 encoded image - decode
            file_format, imgstr = data.split(';base64,')  # format ~= data:image/X;base64,/xxxyyyzzz/
            ext = file_format.split('/')[-1]  # guess file extension
            data = ContentFile(base64.b64decode(imgstr), name='tmp.' + ext)

        return super(StdImageSerializerField, self).to_internal_value(data)


class ImageField(serializers.Field):  # pylint:disable=abstract-method
    """ This field mimics the format of `ImageSerializer`. It is intended to aid the transition away from the
    `Image` model to simple URLs.
    """

    def to_representation(self, value):
        return {
            'src': value,
            'description': None,
            'height': None,
            'width': None
        }
