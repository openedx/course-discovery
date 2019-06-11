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
    # This ordering is mostly alphabetical, for historical reasons. In 2016, we added this CSV endpoint with a nice
    # sensible field ordering (like, key as the first column). In 2018, we broke that ordering and accidentally
    # switched to DRF-CSV's default ordering (alphabetical field names). Which, for the year that it was in the wild,
    # meant that any new course fields would be inserted into the middle, breaking ordering again.
    #
    # Now, I don't know how important ordering *really* is - the headers are labeled, so a sufficiently advanced
    # parser can always find what the key is. But a dumb or just quickly-written parser (like the kind of script a
    # partner might throw together in an afternoon) might reasonably assume columns aren't moving around on them.
    #
    # Anyway. When I noticed this was going on, I froze the alphabetical ordering at the time of writing, to make it
    # easier to assume column ordering and write dumb scripts that ingest this data. New columns will be no longer be
    # automatically appended to the end. So if we want them, we'll need to explicitly add them.
    #
    # (If you're adding new columns, please add them to the end to avoid breaking that theoretically-useful consistent
    # ordering that we now have. Even though that means making this mostly alphabetical list less alphabetical.)
    header = [
        'announcement',
        'content_language',
        'course_key',
        'end',
        'enrollment_end',
        'enrollment_start',
        'expected_learning_items',
        'full_description',
        'image.description',
        'image.height',
        'image.src',
        'image.width',
        'key',
        'level_type',
        'marketing_url',
        'max_effort',
        'min_effort',
        'modified',
        'owners',
        'pacing_type',
        'prerequisites',
        'seats.audit.type',
        'seats.credit.credit_hours',
        'seats.credit.credit_provider',
        'seats.credit.currency',
        'seats.credit.price',
        'seats.credit.type',
        'seats.credit.upgrade_deadline',
        'seats.honor.type',
        'seats.masters.type',
        'seats.professional.currency',
        'seats.professional.price',
        'seats.professional.type',
        'seats.professional.upgrade_deadline',
        'seats.verified.currency',
        'seats.verified.price',
        'seats.verified.type',
        'seats.verified.upgrade_deadline',
        'short_description',
        'sponsors',
        'start',
        'subjects',
        'title',
        'video.description',
        'video.image.description',
        'video.image.height',
        'video.image.src',
        'video.image.width',
        'video.src',
    ]
