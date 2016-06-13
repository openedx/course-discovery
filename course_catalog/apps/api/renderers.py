from rest_framework_xml.renderers import XMLRenderer


class AffiliateWindowXMLRenderer(XMLRenderer):
    """ XML renderer for Affiliate Window product feed.

    Note:
        See http://wiki.affiliatewindow.com/index.php/Product_Feed_Building for the complete spec.
    """
    item_tag_name = 'product'
    root_tag_name = 'merchant'
