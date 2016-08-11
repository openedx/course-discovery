from rest_framework import serializers


class StdImageSerializerField(serializers.Field):
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

    def to_internal_value(self, obj):
        """ We do not need to save/edit this banner image through serializer yet """
        pass
