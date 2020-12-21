import base64
from collections import OrderedDict

from django.core.files.base import ContentFile
from rest_framework import serializers

from course_discovery.apps.course_metadata.utils import clean_html


class StdImageSerializerField(serializers.ImageField):
    """
    Custom serializer field to render out proper JSON representation of the StdImage field on model
    """
    def to_representation(self, value):
        serialized = {}
        for size_key in value.field.variations:
            # Get different sizes specs from the model field
            # Then get the file path from the available files
            sized_file = getattr(value, size_key, None)
            if sized_file:
                path = sized_file.url
                serialized_image = serialized.setdefault(size_key, {})
                # In case MEDIA_URL does not include scheme+host, ensure that the URLs are absolute and not relative
                serialized_image['url'] = self.context['request'].build_absolute_uri(path)
                serialized_image['width'] = value.field.variations[size_key]['width']
                serialized_image['height'] = value.field.variations[size_key]['height']

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

        return super().to_internal_value(data)


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


class HtmlField(serializers.CharField):
    """ Use this class for any model field defined by a HtmlField or NullHtmlField """

    def to_internal_value(self, data):
        """ Cleans incoming HTML to strip some styling that word processors might inject when copying/pasting. """
        data = super().to_internal_value(data)
        return clean_html(data) if data else data


class SlugRelatedTranslatableField(serializers.SlugRelatedField):
    """ Use in place of SlugRelatedField when the slug field is a TranslatedField """

    def to_internal_value(self, data):
        full_translated_field_name = f'translations__{self.slug_field}'
        return self.get_queryset().get(**{full_translated_field_name: data})


class SlugRelatedFieldWithReadSerializer(serializers.SlugRelatedField):
    """
    This field accepts slugs on updates, but provides full serializations on reads.

    This is useful if you want nested serializations, but still want to be able to update the list
    of nested objects with a simple list of slugs.

    The required parameter read_serializer should be an instance of a serializer to use when
    providing a full serialization during read. It does not need 'required' or 'many' parameters to
    be passed. It will always be provided a single object.

    As an example:
        subjects = SlugRelatedFieldWithReadSerializer(slug_field='slug', required=False, many=True,
                                                      queryset=Subject.objects.all(),
                                                      read_serializer=SubjectSerializer())

        update format: {'subjects': ['chemistry']}
        read format: {'subjects': [{'display_name': 'Chemistry', 'slug': 'chemistry'}]}
    """
    def __init__(self, *args, read_serializer=None, **kwargs):
        super().__init__(*args, **kwargs)

        assert read_serializer, 'Must specify a read_serializer to SlugRelatedFieldWithReadSerializer'
        self.read_serializer = read_serializer

        # Connect the child serializer to us, so it can find the root serializer context.
        # field_name='' is just a DRF trick to force the binding.
        self.read_serializer.bind(field_name='', parent=self)

    def to_representation(self, obj):
        return self.read_serializer.to_representation(obj)

    def get_choices(self, cutoff=None):
        """
        This is an exact copy of RelatedField.get_choices, but using slugs instead of to_representation.

        See 'delta' comment below.
        """
        queryset = self.get_queryset()
        if queryset is None:
            # Ensure that field.choices returns something sensible
            # even when accessed with a read-only field.
            return {}

        if cutoff is not None:
            queryset = queryset[:cutoff]

        return OrderedDict([
            (
                # this next line here is the only delta from our parent class: from 'self' to 'super(...)'
                super(SlugRelatedFieldWithReadSerializer, self).to_representation(item),
                self.display_value(item)
            )
            for item in queryset
        ])
