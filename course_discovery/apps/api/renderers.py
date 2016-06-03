from rest_framework_csv.renderers import CSVRenderer
from rest_framework_xml.renderers import XMLRenderer


class AffiliateWindowXMLRenderer(XMLRenderer):
    """ XML renderer for Affiliate Window product feed.

    Note:
        See http://wiki.affiliatewindow.com/index.php/Product_Feed_Building for the complete spec.
    """
    item_tag_name = 'product'
    root_tag_name = 'merchant'


class CourseRunCSVRenderer(CSVRenderer):
    """ CSV renderer for course runs. """
    header = [
        'key',
        'title',
        'pacing_type',
        'start',
        'end',
        'enrollment_start',
        'enrollment_end',
        'announcement',
        'full_description',
        'short_description',
        'marketing_url',
        'image.src',
        'image.description',
        'image.height',
        'image.width',
        'video.src',
        'video.description',
        'video.image.src',
        'video.image.description',
        'video.image.height',
        'video.image.width',
        'content_language',
        'level_type',
        'max_effort',
        'min_effort',
        'subjects',
        'expected_learning_items',
        'prerequisites',
        'owners',
        'sponsors',
        'seats.audit.type',
        'seats.honor.type',
        'seats.professional.type',
        'seats.professional.price',
        'seats.professional.currency',
        'seats.professional.upgrade_deadline',
        'seats.verified.type',
        'seats.verified.price',
        'seats.verified.currency',
        'seats.verified.upgrade_deadline',
        'seats.credit.type',
        'seats.credit.price',
        'seats.credit.currency',
        'seats.credit.upgrade_deadline',
        'seats.credit.credit_provider',
        'seats.credit.credit_hours',
        'modified',
    ]
