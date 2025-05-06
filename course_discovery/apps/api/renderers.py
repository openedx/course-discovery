from rest_framework_csv.renderers import CSVStreamingRenderer
from rest_framework_xml.renderers import XMLRenderer


class AffiliateWindowXMLRenderer(XMLRenderer):
    """ XML renderer for Affiliate Window product feed.

    Note:
        See http://wiki.affiliatewindow.com/index.php/Product_Feed_Building for the complete spec.
    """
    item_tag_name = 'product'
    root_tag_name = 'merchant'


class CourseRunCSVRenderer(CSVStreamingRenderer):
    """ CSV renderer for course runs. """
    header = [
        'key',
        'title',
        'start',
        'end',
        'enrollment_start',
        'enrollment_end',
        'modified',
    ]
