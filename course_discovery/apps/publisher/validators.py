from bs4 import BeautifulSoup
from django import forms
from django.core.exceptions import ValidationError
from django.utils.translation import ugettext_lazy as _
from stdimage.validators import BaseSizeValidator


class ImageSizeValidator(BaseSizeValidator):
    """
    ImageField validator to validate the width and height of an image.
    NOTE: This is not used in the current models. But it was used in model migrations
    """

    def compare(self, img_size, limit_size):  # pylint: disable=arguments-differ
        return img_size[0] != limit_size[0] or img_size[1] != limit_size[1]

    message = _(
        'The image you uploaded is of incorrect resolution. '
        'Course image files must be %(with)s x %(height)s pixels in size.'
    )


class ImageMultiSizeValidator(ImageSizeValidator):
    """
    ImageField Size validator that takes in a list of sizes to validate
    Will pass validation if the image is of one of the specified size
    """
    def __init__(self, supported_sizes, **kwargs):  # pylint: disable=super-init-not-called
        self.supported_sizes = supported_sizes
        self.preferred_size = kwargs.get('preferred_size')
        if not self.preferred_size:
            self.preferred_size = self.supported_sizes.pop()

    def __call__(self, value):
        cleaned = self.clean(value)
        validated = False
        limit_sizes = [self.preferred_size]
        limit_sizes.extend(self.supported_sizes)
        for limit_size in limit_sizes:
            if not self.compare(cleaned, limit_size):
                validated = True
        if not validated:
            supported_sizes_message_array = []
            for size in self.supported_sizes:
                supported_sizes_message_array.append(
                    '{} X {} px'.format(size[0], size[1])
                )
            params = {
                'preferred': '{} X {} pixels'.format(self.preferred_size[0], self.preferred_size[1]),
                'supported': ' or '.join(supported_sizes_message_array)
            }
            raise ValidationError(self.message, code=self.code, params=params)

    message = _(
        'Invalid image size. The recommended image size is %(preferred)s. '
        'Older courses also support image sizes of %(supported)s.'
    )


def validate_text_count(max_length):
    """
    Custom validator to count the text area characters without html tags.
    """
    def innerfn(raw_html):
        cleantext = BeautifulSoup(raw_html, 'html.parser').get_text(strip=True)
        if len(cleantext) > max_length:
            raise forms.ValidationError(
                _('Ensure this value has at most {allowed_char} characters (it has {current_char}).').format(
                    allowed_char=max_length,
                    current_char=len(cleantext)
                )
            )
    return innerfn
