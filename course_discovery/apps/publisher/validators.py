from django.core.exceptions import ValidationError
from stdimage.validators import BaseSizeValidator


class ImageSizeValidator(BaseSizeValidator):
    """
    ImageField validator to validate the width and height of an image.
    NOTE: This is not used in the current models. But it was used in model migrations
    """

    def compare(self, img_size, limit_size):  # pylint: disable=arguments-differ
        return img_size[0] != limit_size[0] or img_size[1] != limit_size[1]

    message = (
        'The image you uploaded is of incorrect resolution. '
        'Course image files must be %(with)s x %(height)s pixels in size.'
    )


class ImageMultiSizeValidator(ImageSizeValidator):
    """
    ImageField Size validator that takes in a list of sizes to validate
    Will pass validation if the image is of one of the specified size
    NOTE: This is not used in the current models. But it was used in model migrations
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

    message = (
        'Invalid image size. The recommended image size is %(preferred)s. '
        'Older courses also support image sizes of %(supported)s.'
    )
