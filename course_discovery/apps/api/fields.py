import base64

from rest_framework import serializers
from django.core.files.base import ContentFile


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

class WritableSerializerMethodField(serializers.SerializerMethodField):
    """
    A read-write field that get its representation from calling a method on the
    parent serializer class. The method called will be of the form
    "get_{field_name}", and should take a single argument, which is the
    object being serialized.
    For example:
    class ExampleSerializer(self):
        extra_info = SerializerMethodField()
        def get_extra_info(self, obj):
            return ...  # Calculate some data to return.
    """
    def __init__(self, write_method_name=None, **kwargs):
        super(WritableSerializerMethodField, self).__init__(**kwargs)
        self.write_method_name = write_method_name
        self.read_only = False

    def bind(self, field_name, parent):
        # In order to enforce a consistent style, we error if a redundant
        # 'write_method_name' argument has been used. For example:
        # my_field = serializer.SerializerMethodField(write_method_name='set_my_field')
        default_write_method_name = 'set_{field_name}'.format(field_name=field_name)
        assert self.write_method_name != default_write_method_name, (
            "It is redundant to specify `%s` on SerializerMethodField '%s' in "
            "serializer '%s', because it is the same as the default write method name. "
            "Remove the `write_method_name` argument." %
            (self.write_method_name, field_name, parent.__class__.__name__)
        )

        # The method name should default to `set_{field_name}`.
        if self.write_method_name is None:
            self.write_method_name = default_write_method_name

        super(WritableSerializerMethodField, self).bind(field_name, parent)

    def to_internal_value(self, obj):
        write_method = getattr(self.parent, self.write_method_name)
        return write_method(obj)
