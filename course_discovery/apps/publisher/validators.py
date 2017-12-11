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
    def __init__(self, limit_sizes):  # pylint: disable=super-init-not-called
        self.limit_value = limit_sizes

    def __call__(self, value):
        cleaned = self.clean(value)
        validated = False
        for limit_size in self.limit_value:
            if not self.compare(cleaned, limit_size):
                validated = True
        if not validated:
            size_message_array = []
            for limit_size in self.limit_value:
                size_message_array.append(
                    '({} X {})'.format(limit_size[0], limit_size[1])
                )
            params = {
                'sizes': ', '.join(size_message_array)
            }
            raise ValidationError(self.message, code=self.code, params=params)

    message = _(
        'The image you uploaded is of incorrect resolution. '
        'Course image files must be in one of the following sizes in pixels: %(sizes)s'
    )


def validate_text_count(max_length):
    """
    Custom validator to count the text area characters without html tags.
    """
    def innerfn(raw_html):
        cleantext = BeautifulSoup(raw_html, 'html.parser').text.strip()

        if len(cleantext) > max_length:
            # pylint: disable=no-member
            raise forms.ValidationError(
                _('Ensure this value has at most {allowed_char} characters (it has {current_char}).').format(
                    allowed_char=max_length,
                    current_char=len(cleantext)
                )
            )
    return innerfn
