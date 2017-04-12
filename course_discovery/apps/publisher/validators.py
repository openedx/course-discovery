from bs4 import BeautifulSoup
from django import forms
from django.utils.translation import ugettext_lazy as _
from stdimage.validators import BaseSizeValidator


class ImageSizeValidator(BaseSizeValidator):
    """
    ImageField validator to validate the width and height of an image.
    """

    def compare(self, img_size, limit_size):  # pylint: disable=arguments-differ
        return img_size[0] != limit_size[0] or img_size[1] != limit_size[1]

    message = _(
        'The image you uploaded is of incorrect resolution. '
        'Course image files must be %(with)s x %(height)s pixels in size.'
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
