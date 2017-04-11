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
