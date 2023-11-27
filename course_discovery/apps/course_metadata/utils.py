import datetime
import logging
import random
import re
import string
import uuid
from tempfile import NamedTemporaryFile
from urllib.parse import urljoin, urlparse

import html2text
import markdown
import requests
from bs4 import BeautifulSoup
from cairosvg import svg2png
from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.files.base import ContentFile
from django.db import models, transaction
from django.utils.functional import cached_property
from django.utils.translation import gettext as _
from dynamic_filenames import FilePattern
from getsmarter_api_clients.geag import GetSmarterEnterpriseApiClient
from slugify import slugify
from stdimage.models import StdImageFieldFile

from course_discovery.apps.core.models import SalesforceConfiguration
from course_discovery.apps.core.utils import serialize_datetime
from course_discovery.apps.course_metadata.constants import (
    DEFAULT_SLUG_FORMAT_ERROR_MSG, HTML_TAGS_ATTRIBUTE_WHITELIST, IMAGE_TYPES, SLUG_FORMAT_REGEX,
    SUBDIRECTORY_SLUG_FORMAT_REGEX
)
from course_discovery.apps.course_metadata.exceptions import (
    EcommerceSiteAPIClientException, MarketingSiteAPIClientException
)
from course_discovery.apps.course_metadata.googleapi_client import GoogleAPIClient
from course_discovery.apps.course_metadata.salesforce import SalesforceUtil
from course_discovery.apps.course_metadata.toggles import (
    IS_COURSE_RUN_VARIANT_ID_ECOMMERCE_CONSUMABLE, IS_SUBDIRECTORY_SLUG_FORMAT_ENABLED
)
from course_discovery.apps.publisher.utils import VALID_CHARS_IN_COURSE_NUM_AND_ORG_KEY

logger = logging.getLogger(__name__)

RESERVED_ELASTICSEARCH_QUERY_OPERATORS = ('AND', 'OR', 'NOT', 'TO',)


def clean_query(query):
    """ Prepares a raw query for search.

    Args:
        query (str): query to clean.

    Returns:
        str: cleaned query
    """

    # Specifying a SearchQuerySet filter will append an explicit AND clause to the query, thus changing its semantics.
    # So we wrap parentheses around the original query in order to preserve the semantics.
    query = f'({query})'

    # Ensure all operators are uppercase
    for operator in RESERVED_ELASTICSEARCH_QUERY_OPERATORS:
        old = f' {operator.lower()} '
        new = f' {operator.upper()} '
        query = query.replace(old, new)

    return query


def set_official_state(obj, model, attrs=None):
    """
    Given a draft object and the model of that object, ensure that an official version is created
    or updated to match the draft version and set the attributes of that object accordingly.

    Args
        obj (instance of a model class)
        model (model class of that object)
        attrs (dictionary of attributes to set on the official version of the object)

    Returns
        the official version of that object with the attributes updated to attrs
    """
    # pylint: disable=import-outside-toplevel
    from course_discovery.apps.course_metadata.models import Course, CourseRun

    # This is so we don't create the marketing node with an incorrect slug.
    # We correct the slug after setting official state, but the AutoSlugField initially overwrites it.
    if isinstance(obj, CourseRun):
        save_kwargs = {'suppress_publication': True}
    else:
        save_kwargs = {}
    if obj.draft:
        official_obj = obj.official_version
        draft_version = model.everything.get(pk=obj.pk)

        obj.pk = official_obj.pk if official_obj else None  # pk=None will create it if it didn't exist.
        obj.draft = False
        obj.draft_version = draft_version
        if isinstance(obj, Course):
            obj.canonical_course_run = official_obj.canonical_course_run if official_obj else None
        obj.save(**save_kwargs)
        official_obj = obj
        # Copy many-to-many fields manually (they are not copied by the pk trick above).
        # This must be done after the save() because we need an id.
        for field in model._meta.get_fields():
            if field.many_to_many and not field.auto_created:
                getattr(official_obj, field.name).clear()
                # TEMPORARY - log stack trace when subjects are cleared and not re-filled, see Jira DISCO-1593
                if field.name == "subjects" and draft_version.subjects.count() == 0:
                    logger.error('Adding empty subject list to published course', stack_info=True)
                getattr(official_obj, field.name).add(*list(getattr(draft_version, field.name).all()))

    else:
        official_obj = obj

    # Now set fields we were told to
    if attrs:
        for key, value in attrs.items():
            setattr(official_obj, key, value)
        official_obj.save(**save_kwargs)

    return official_obj


def set_draft_state(obj, model, attrs=None, related_attrs=None):
    """
    Sets the draft state for an object by giving it a new primary key. Also sets any given
    attributes (primarily used for setting foreign keys that also point to draft rows). This will
    make any additional operations on the object to be done to the new draft state object.

    Parameters:
        obj (Model object): The object to create a draft state for. *Must have draft and draft_version as attributes.*
        model (Model class): the model class so it can be used to get the original object
        attrs ({str: value}): Dictionary of attributes to set on the draft model. The key should be the
            attribute name as a string and the value should be the value to set.

    Returns:
        (Model obj, Model obj): Tuple of Model objects where the first is the draft object
            and the second is the original
    """
    # pylint: disable=import-outside-toplevel
    from course_discovery.apps.course_metadata.models import Course, CourseRun
    original_obj = model.objects.get(pk=obj.pk)
    obj.pk = None
    obj.draft = True

    # Now set fields we were told to
    if attrs:
        for key, value in attrs.items():
            setattr(obj, key, value)

    obj.save()

    # must be done after save so we have an id
    if related_attrs:
        for key, value in related_attrs.items():
            getattr(obj, key).set(value)

    # We refresh the object's instance before we set its salesforce_id because the instance in memory is
    # out of sync with what is actually in the database.  The salesforce_id is indeed in the database at this point
    # because we generate it on a post_save signal for Course's and CourseRun's.
    if model in (Course, CourseRun):
        obj.refresh_from_db()
        original_obj.salesforce_id = obj.salesforce_id

    original_obj.draft_version = obj
    original_obj.save()

    # Copy many-to-many fields manually (they are not copied by the pk=None trick above).
    # This must be done after the save() because we need an id.
    for field in model._meta.get_fields():
        if field.many_to_many and not field.auto_created:
            getattr(obj, field.name).add(*list(getattr(original_obj, field.name).all()))

    return obj, original_obj


def _calculate_entitlement_for_run(run):
    from course_discovery.apps.course_metadata.models import Seat  # pylint: disable=import-outside-toplevel

    entitlement_seats = [seat for seat in run.seats.all() if seat.type.slug in Seat.ENTITLEMENT_MODES]
    if len(entitlement_seats) != 1:
        return None

    seat = entitlement_seats[0]
    return seat.type.slug, seat.price, seat.currency


def _calculate_entitlement_for_course(course):
    # pylint: disable=import-outside-toplevel
    from course_discovery.apps.course_metadata.models import Course

    # When we are creating the draft course for the first time, the prefetch_related of course runs
    # on the serializer causes any related key lookups on course.course_runs return an empty
    # QuerySet despite knowing it exists. So we use the below check to see if we are in this case,
    # and if so, to get the course to re-establish the course.course_runs relationship.
    if course.course_runs.exists() and not course.course_runs.last():
        course = Course.everything.get(pk=course.pk)

    # Get all active runs or latest inactive run
    runs = course.active_course_runs
    if not runs and course.course_runs.exists():
        runs = [course.course_runs.last()]
    if not runs:
        return None

    entitlement_data = {_calculate_entitlement_for_run(run) for run in runs}
    if len(entitlement_data) > 1:
        return None  # some runs disagree - we can't form an entitlement from this
    return entitlement_data.pop()


def create_missing_entitlement(course):
    """
    Add an entitlement to a course, based on current seats, if possible.

    Returns:
        True if an entitlement was created, False if we could not make one
    """
    # pylint: disable=import-outside-toplevel
    from course_discovery.apps.course_metadata.models import CourseEntitlement, SeatType

    calculated_entitlement = _calculate_entitlement_for_course(course)
    if calculated_entitlement:
        mode, price, currency = calculated_entitlement
        CourseEntitlement.objects.create(
            course=course,
            mode=SeatType.objects.get(slug=mode),
            partner=course.partner,
            price=price,
            currency=currency,
            draft=course.draft,
        )

        if not course.draft and course.canonical_course_run:
            # We should tell ecommerce about this new entitlement.
            # We need to provide a run (based on how ecommerce accepts the push request).
            # But the run we provide doesn't matter - we're not changing its seats at all.
            # Since we know that the canonical run should already be published in ecommerce, just use it.
            push_to_ecommerce_for_course_run(course.canonical_course_run)

        return True

    return False


def ensure_draft_world(obj):
    """
    Ensures the draft world exists for an object. The draft world is defined as all draft objects related to
    the incoming draft object. For now, this will create the draft Course, all draft Course Runs associated
    with that course, all draft Seats associated with all of the course runs, and all draft Entitlements
    associated with the course.

    Assumes that if the given object is already a draft, the draft world for that object already exists.

    Parameters:
        obj (Model object): The object to create a draft state for. *Must have draft as an attribute.*

    Returns:
        obj (Model object): The returned object will be the draft version on the input object.
    """
    # pylint: disable=import-outside-toplevel
    from course_discovery.apps.course_metadata.models import Course, CourseEntitlement, CourseRun, Seat
    if obj.draft:
        return obj
    elif obj.draft_version:
        return obj.draft_version

    if isinstance(obj, CourseRun):
        ensure_draft_world(obj.course)
        return CourseRun.everything.get(key=obj.key, draft=models.Value(1))

    elif isinstance(obj, Course):
        # We need to null this out because it will fail with a OneToOne uniqueness error when saving the draft
        obj.canonical_course_run = None
        draft_course, original_course = set_draft_state(obj, Course, related_attrs={'url_slug_history': []})

        # Move editors from the original course to the draft course since we only care about CourseEditors
        # in the context of draft courses. This code is only necessary during the transition from using
        # Publisher in this repo to the Publisher Microfrontend.
        for editor in original_course.editors.all():
            editor.course = draft_course
            editor.save()

        # Create draft course runs, the corresponding draft seats, and the draft entitlement
        for run in original_course.course_runs.all():
            draft_run, original_run = set_draft_state(run, CourseRun, {'course': draft_course})
            draft_run.slug = original_run.slug
            draft_run.save()

            for seat in original_run.seats.all():
                set_draft_state(seat, Seat, {'course_run': draft_run})
            if original_course.canonical_course_run and draft_run.uuid == original_course.canonical_course_run.uuid:
                draft_course.canonical_course_run = draft_run

        if original_course.entitlements.exists():
            for entitlement in original_course.entitlements.all():
                set_draft_state(entitlement, CourseEntitlement, {'course': draft_course})
        else:
            create_missing_entitlement(draft_course)

        draft_course.save()
        # must re-get from db to ensure related fields like course_runs are updated (refresh_from_db isn't enough)
        return Course.everything.get(pk=draft_course.pk)
    else:
        raise Exception(  # pylint: disable=broad-exception-raised
            'Ensure draft world only accepts Courses and Course Runs.'
        )


class UploadToFieldNamePath(FilePattern):
    """
    This is a utility to create file path for uploads based on instance field value
    """
    filename_pattern = '{path}{name}{ext}'

    def __init__(self, populate_from, **kwargs):
        self.populate_from = populate_from
        kwargs['populate_from'] = populate_from
        if kwargs['path'] and not kwargs['path'].endswith('/'):
            kwargs['path'] += '/'
        super().__init__(**kwargs)

    def __call__(self, instance, filename):
        field_value = getattr(instance, self.populate_from)
        # Update name with Random string of 12 character at the end example '-ba123cd89e97'
        self.override_values.update({
            'name': str(field_value) + str(uuid.uuid4())[23:]
        })
        return super().__call__(instance, filename)


def custom_render_variations(file_name, variations, storage, replace=True):
    """ Utility method used to override default behaviour of StdImageFieldFile by
    passing it replace=True.

    Args:
        file_name (str): name of the image file.
        variations (dict): dict containing variations of image
        storage (Storage): Storage class responsible for storing the image.

    Returns:
        False (bool): to prevent its default behaviour
    """

    for variation in variations.values():
        StdImageFieldFile.render_variation(file_name, variation, replace, storage)

    # to prevent default behaviour
    return False


def parse_course_key_fragment(fragment):
    """
    Parses a course key fragment like "edX+DemoX" or "edX/DemoX" into org and course number. We call this a fragment,
    because this kind of "course key" is not to be confused with the CourseKey class that parses a full course run key
    like "course-v1:edX+DemoX+1T2019".

    Returns a two values: (org, course number). If the key could not be parsed, then ValueError is raised.
    """
    split = fragment.split('/') if '/' in fragment else fragment.split('+')
    if len(split) != 2:
        raise ValueError(f'Could not understand course key fragment "{fragment}".')
    return split[0], split[1]


def validate_course_number(course_number):
    """
    Verifies that the Course Number does not contain invalid characters. Raises a ValueError if there are
    invalid characters.

    Args:
        course_number: Course Number String
    """
    if not VALID_CHARS_IN_COURSE_NUM_AND_ORG_KEY.match(course_number):
        raise ValueError(_('Special characters not allowed in Course Number.'))


def get_course_run_estimated_hours(course_run):
    """
    Returns the average estimated work hours to complete the course run.

    Args:
        course_run: Course Run object.
    """
    min_effort = course_run.min_effort or 0
    max_effort = course_run.max_effort or 0
    weeks_to_complete = course_run.weeks_to_complete or 0
    effort = min_effort + max_effort
    return (effort / 2) * weeks_to_complete if effort and weeks_to_complete else 0


def subtract_deadline_delta(end, delta):
    deadline = end - datetime.timedelta(days=delta)
    deadline = deadline.replace(hour=23, minute=59, second=59, microsecond=99999)
    return deadline


def calculated_seat_upgrade_deadline(seat):
    """ Returns upgraded deadline calculated using edX business logic.

    Only verified seats have upgrade deadlines. If the instance does not have an upgrade deadline set, the value
    will be calculated based on the related course run's end date.
    """
    slug = seat.type if isinstance(seat.type, str) else seat.type.slug
    if slug == seat.VERIFIED:
        if seat.upgrade_deadline:
            return seat.upgrade_deadline

        if not seat.course_run.end:
            return None

        return subtract_deadline_delta(seat.course_run.end, settings.PUBLISHER_UPGRADE_DEADLINE_DAYS)

    return None


def serialize_seat_for_ecommerce_api(seat, mode):
    """
    Serializes seat data for ecommerce publication API.
    """
    attribute_values_list = [
        {
            'name': 'certificate_type',
            'value': mode.certificate_type,
        },
        {
            'name': 'id_verification_required',
            'value': mode.is_id_verified,
        }
    ]

    if IS_COURSE_RUN_VARIANT_ID_ECOMMERCE_CONSUMABLE.is_enabled():
        course_run = seat.course_run
        if course_run and course_run.variant_id:
            attribute_values_list.append({
                'name': 'variant_id',
                'value': str(course_run.variant_id),
            })

    return {
        'expires': serialize_datetime(calculated_seat_upgrade_deadline(seat)),
        'price': str(seat.price),
        'product_class': 'Seat',
        'stockrecords': [{'partner_sku': getattr(seat, 'sku', None)}],
        'attribute_values': attribute_values_list,
    }


def serialize_entitlement_for_ecommerce_api(entitlement):
    """
    Serializes entitlement data for ecommerce publication API.
    """
    attribute_values_list = [
        {
            'name': 'certificate_type',
            'value': entitlement.mode if isinstance(entitlement.mode, str) else entitlement.mode.slug,
        },
    ]

    if IS_COURSE_RUN_VARIANT_ID_ECOMMERCE_CONSUMABLE.is_enabled():
        course = entitlement.course
        if course.advertised_course_run and course.advertised_course_run.variant_id:
            attribute_values_list.append({
                'name': 'variant_id',
                'value': str(course.advertised_course_run.variant_id),
            })
    else:
        additional_metadata = entitlement.course.additional_metadata
        if additional_metadata and additional_metadata.variant_id:
            attribute_values_list.append({
                'name': 'variant_id',
                'value': str(additional_metadata.variant_id),
            })

    return {
        'price': str(entitlement.price),
        'product_class': 'Course Entitlement',
        'attribute_values': attribute_values_list,
    }


def push_to_ecommerce_for_course_run(course_run):
    """
    Args:
        course_run: Official version of a course_metadata CourseRun
    """
    course = course_run.course
    if not course.partner.ecommerce_api_url:
        return False

    api = course.partner.oauth_api_client
    entitlements = course.entitlements.all()

    # Figure out which seats to send (skip ones that have no ecom products - like Masters - or are just misconfigured).
    # This is dumb and does basically a O(n^2) inner join here to match seats to modes. I feel like the Django
    # ORM has a better solution for this, but I couldn't find it easily. These lists are small anyway.
    tracks = course_run.type.tracks.all()
    seats_with_modes = []
    for seat in course_run.seats.all():
        for track in tracks:
            if track.seat_type and seat.type == track.seat_type:
                seats_with_modes.append((seat, track.mode))
                break

    discovery_products = []
    serialized_products = []
    if seats_with_modes:
        serialized_products.extend([serialize_seat_for_ecommerce_api(s[0], s[1]) for s in seats_with_modes])
        discovery_products.extend([s[0] for s in seats_with_modes])
    if entitlements:
        serialized_products.extend([serialize_entitlement_for_ecommerce_api(e) for e in entitlements])
        discovery_products.extend(list(entitlements))
    if not serialized_products:
        return False  # nothing to do

    url = urljoin(course.partner.ecommerce_api_url, 'publication/')
    response = api.post(url, json={
        'id': course_run.key,
        'uuid': str(course.uuid),
        'name': course_run.title,
        'verification_deadline': serialize_datetime(course_run.end),
        'products': serialized_products,
    })

    if 400 <= response.status_code < 600:
        error = response.json().get('error')
        if error:
            raise EcommerceSiteAPIClientException({'error': error})
        response.raise_for_status()

    # Now save the returned SKU numbers locally
    ecommerce_products = response.json().get('products', [])
    if len(discovery_products) == len(ecommerce_products):
        with transaction.atomic():
            for i, discovery_product in enumerate(discovery_products):
                ecommerce_product = ecommerce_products[i]
                sku = ecommerce_product.get('partner_sku')
                if not sku:
                    continue

                discovery_product.sku = sku
                discovery_product.save()

                if discovery_product.draft_version:
                    discovery_product.draft_version.sku = sku
                    discovery_product.draft_version.save()

    return True


def push_tracks_to_lms_for_course_run(course_run):
    """
    Notifies the LMS about this course run's entitlement modes.

    Currently, this only actually does anything for entitlement modes without a seat. Other enrollment modes are
    instead handled by Discovery pushing to E-Commerce, and the LMS then pulls that info in separately.

    Eventually, we might want to consider handling all track types here and short-cutting that cycle by pushing
    directly to LMS. But that's a future improvement.
    """
    run_type = course_run.type
    tracks_without_seats = run_type.tracks.filter(seat_type=None)
    if not tracks_without_seats:
        return

    partner = course_run.course.partner
    if not partner.lms_coursemode_api_url:
        logger.info('No LMS coursemode api url configured. Cannot publish LMS tracks for [%s].', course_run.key)
        return

    url = partner.lms_coursemode_api_url.rstrip('/') + f'/courses/{course_run.key}/'
    course_modes = {mode['mode_slug'] for mode in partner.oauth_api_client.get(url).json()}

    for track in tracks_without_seats:
        if track.mode.slug in course_modes:
            # We already have this mode on the LMS side!
            continue

        data = {
            'course_id': course_run.key,
            'mode_slug': track.mode.slug,
            'mode_display_name': track.mode.name,
            'currency': 'usd',
            'min_price': 0,
        }
        response = partner.oauth_api_client.post(url, json=data)

        if response.ok:
            logger.info('Successfully published [%s] LMS mode for [%s].', track.mode.slug, course_run.key)
        else:
            logger.warning('Failed publishing [%s] LMS mode for [%s]: %s', track.mode.slug, course_run.key,
                           response.content.decode('utf-8'))


class MarketingSiteAPIClient:
    """
    The marketing site API client we can use to communicate with the marketing site
    """
    username = None
    password = None
    api_url = None

    def __init__(self, marketing_site_api_username, marketing_site_api_password, api_url):
        if not (marketing_site_api_username and marketing_site_api_password):
            raise MarketingSiteAPIClientException('Marketing Site API credentials are not properly configured!')
        self.username = marketing_site_api_username
        self.password = marketing_site_api_password
        self.api_url = api_url.strip('/')

    @cached_property
    def init_session(self):
        # Login to set session cookies
        session = requests.Session()
        login_url = f'{self.api_url}/user'
        login_data = {
            'name': self.username,
            'pass': self.password,
            'form_id': 'user_login',
            'op': 'Log in',
        }
        response = session.post(login_url, data=login_data)
        admin_url = f'{self.api_url}/admin'
        # This is not a RESTful API so checking the status code is not enough
        # We also check that we were redirected to the admin page
        if not (response.status_code == 200 and response.url == admin_url):
            raise MarketingSiteAPIClientException(
                {
                    'message': 'Marketing Site Login failed!',
                    'status': response.status_code,
                    'url': response.url
                }
            )
        return session

    @property
    def api_session(self):
        self.init_session.headers.update(self.headers)
        return self.init_session

    @property
    def csrf_token(self):
        # We need to make sure we can bypass the Varnish cache.
        # So adding a random salt into the query string to cache bust
        random_qs = ''.join(random.choice(string.ascii_uppercase + string.digits) for _ in range(10))
        token_url = f'{self.api_url}/restws/session/token?cachebust={random_qs}'
        response = self.init_session.get(token_url)
        if not response.status_code == 200:
            raise MarketingSiteAPIClientException({
                'message': 'Failed to retrieve Marketing Site CSRF token!',
                'status': response.status_code,
            })
        token = response.content.decode('utf8')
        return token

    @cached_property
    def user_id(self):
        # Get a user ID
        user_url = f'{self.api_url}/user.json?name={self.username}'
        response = self.init_session.get(user_url)
        if not response.status_code == 200:
            raise MarketingSiteAPIClientException('Failed to retrieve Marketing site user details!')
        user_id = response.json()['list'][0]['uid']
        return user_id

    @property
    def headers(self):
        return {
            'Content-Type': 'application/json',
            'X-CSRF-Token': self.csrf_token,
        }


def get_salesforce_util(partner):
    try:
        return SalesforceUtil(partner)
    except SalesforceConfiguration.DoesNotExist:
        return None


class HTML2TextWithLangSpans(html2text.HTML2Text):
    # pylint: disable=abstract-method

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.ignore_links = True
        self.in_lang_span = False
        self.images_with_size = True
        self.is_p_tag_with_dir = False

    def add_and_filter_attrs(self, tag, dict_attrs):
        """
        This method adds only allowed attributes to the whitelisted tags
        """
        self.outtextf(f'<{tag}')
        filtered_attrs_list = [
            (attr, value) for attr, value in dict_attrs.items()
            if attr in HTML_TAGS_ATTRIBUTE_WHITELIST[tag]
        ]
        for attr, value in filtered_attrs_list:
            self.outtextf(f' {attr}="{value}"')
        self.outtextf('>')

    def whitelist_html_tags_attribute(self, tag, dict_attrs, start):
        """
        This method overrides the default behavior of html2text to include only allowed tags from attr_dict
        because by default it only includes the href and title attributes for <a> tags and
        discards the dir attribrute for <p> tags
        """
        if tag in HTML_TAGS_ATTRIBUTE_WHITELIST:
            if start:
                if HTML_TAGS_ATTRIBUTE_WHITELIST[tag][0] in dict_attrs:
                    if tag == 'p':
                        self.is_p_tag_with_dir = True
                    self.add_and_filter_attrs(tag, dict_attrs)
            elif (tag == 'p' and self.is_p_tag_with_dir) or (tag == 'a'):
                if tag == 'p':
                    self.is_p_tag_with_dir = False
                self.outtextf(f'</{tag}>')

    def handle_tag(self, tag, attrs, start):
        """
        This method overrides the default behavior of html2text behavior for <span> tags (adding 'lang' attribute)
        and <p> tags (adding 'dir' attribute). Additionally, within <p dir="rtl"> tags, it retains the original text
        format to ensure consistent handling, addressing an issue where inner HTML content was not converting back to
        HTML.
        """
        if not self.is_p_tag_with_dir:
            super().handle_tag(tag, attrs, start)

        elif tag not in HTML_TAGS_ATTRIBUTE_WHITELIST:
            if start:
                self.outtextf(f'<{tag}')
                if attrs:
                    self.outtextf(' ')
                    self.outtextf(' '.join(f'{attr}="{value}"' for attr, value in attrs.items()))
                self.outtextf('>')
            else:
                self.outtextf(f'</{tag}>')

        if tag == 'span':
            if attrs and start and 'lang' in dict(attrs):
                self.outtextf(f'<span lang="{dict(attrs)["lang"]}">')
                self.in_lang_span = True
            if not start and self.in_lang_span:
                self.outtextf('</span>')
                self.in_lang_span = False
        self.whitelist_html_tags_attribute(tag, dict(attrs), start)


def clean_html(content):
    """
    Cleans HTML from a string.

    This method converts the HTML to a Markdown string (to remove styles, classes, and other unsupported
    attributes), and converts the Markdown back to HTML. This is done to ensure that the HTML is as clean as
    possible, and that it is consistent with the HTML that is generated by the tinymce editor.

    Additionally, if certain HTML tags (e.g., <ul>, <ol>) contain the 'dir' attribute with the value 'rtl'
    (indicating right-to-left direction), this method will ensure that the 'dir' attribute is preserved
    or added to maintain consistency with the original content.
    """
    LIST_TAGS = ['ul', 'ol']
    is_list_with_dir_attr_present = False

    cleaned = content.replace('&nbsp;', '')  # Keeping the removal of nbsps for historical consistency
    # Parse the HTML using BeautifulSoup
    soup = BeautifulSoup(cleaned, 'lxml')

    for tag in soup.find_all(LIST_TAGS, dir="rtl"):
        tag.attrs.pop('dir')
        is_list_with_dir_attr_present = True

    cleaned = str(soup)
    # Need to re-replace the · middot with the entity so that html2text can transform it to * for <ul> in markdown
    cleaned = cleaned.replace('·', '&middot;')
    # Need to clean empty <b> and <p> tags which are converted to <hr/> by html2text
    cleaned = cleaned.replace('<p><b></b></p>', '')
    html_converter = HTML2TextWithLangSpans(bodywidth=None)
    html_converter.wrap_links = False
    cleaned = html_converter.handle(cleaned).strip()
    cleaned = markdown.markdown(cleaned)
    for tag in LIST_TAGS:
        cleaned = cleaned.replace(f'<{tag}>', f'<{tag} dir="rtl">') if is_list_with_dir_attr_present else cleaned

    return cleaned


def get_file_from_drive_link(image_url):
    """
    Helper method to get the file content_type and content from a drive link

    Keyword Arguments:
        image_url {str} -- drive link of the file

    Returns:
        tuple --  content_type and content of the file
    """
    google_api_client = GoogleAPIClient()
    content_type = google_api_client.get_file_metadata(image_url).get('mimeType')
    content = google_api_client.download_file_by_url(image_url)
    return content_type, content


def download_and_save_course_image(course, image_url, data_field='image', headers=None):
    """
    Helper method to download an image from a provided image url and save it
    in the data field mentioned, defaulting to course card image.
    """
    try:
        if is_google_drive_url(image_url):
            content_type, content = get_file_from_drive_link(image_url)
            extension = IMAGE_TYPES.get(content_type)
        else:
            response = requests.get(image_url, headers=headers)  # pylint: disable=missing-timeout

            if response.status_code == requests.codes.ok:  # pylint: disable=no-member
                content_type = response.headers['Content-Type'].lower()
                extension = IMAGE_TYPES.get(content_type)
                content = response.content

            else:
                msg = 'Failed to download image for course [%s] from [%s]! Response was [%d]:\n%s'
                logger.error(msg, course.key, image_url, response.status_code, response.content)
                return False

        if extension:
            filename = '{uuid}.{extension}'.format(uuid=str(course.uuid), extension=extension)
            # TODO: Get field from _meta.get_field. Tried that approach initially but was getting
            # field save errors for some reasons.
            if data_field == 'image':
                course.image.save(filename, ContentFile(content))
            elif data_field == 'organization_logo_override':
                image_file = ContentFile(content)
                if extension == 'svg':
                    filename = '{uuid}.png'.format(uuid=str(course.uuid))
                    image_file = convert_svg_to_png_from_url(image_url)
                if image_file:
                    course.organization_logo_override.save(filename, image_file)
                else:
                    logger.error('Update organization logo override failed for course [%s]', course.key)
                    return False
            logger.info(f'Image for course {course.key} successfully updated in {data_field} field')
            return True
        else:
            msg = 'Image retrieved for course [%s] from [%s] has an unknown content type [%s] and will not be saved.'
            logger.error(msg, course.key, image_url, content_type)

    except Exception:  # pylint: disable=broad-except
        logger.exception('An unknown exception occurred while downloading image for course [%s]', course.key)
    return False


def convert_svg_to_png_from_url(image_url):
    """
    Given an image file url of svg, it will convert that svg image to png
    and save in temporary file
    """
    try:
        temp_file = NamedTemporaryFile()  # lint-amnesty, pylint: disable=consider-using-with
        svg2png(url=image_url, write_to=temp_file.name)
        temp_file.seek(0)
        return temp_file
    except Exception:  # pylint: disable=broad-except
        logger.exception('An unknown exception occurred while converting image [%s]', image_url)
        return None


def is_google_drive_url(url):
    """
    Helper method to check if the file url is a drive url or not
    """
    parsed_url = urlparse(url)
    return parsed_url.hostname == 'drive.google.com'


def download_and_save_program_image(program, image_url, data_field='image', headers=None):
    """
    Helper method to download an image from a provided image url and save it
    in the data field mentioned, defaulting to program card image.
    """
    # TODO: refactor and merge program image download to use the same code as course image download
    try:
        if is_google_drive_url(image_url):
            content_type, content = get_file_from_drive_link(image_url)
            extension = IMAGE_TYPES.get(content_type)
        else:
            response = requests.get(image_url, headers=headers)  # pylint: disable=missing-timeout

            if response.status_code == requests.codes.ok:  # pylint: disable=no-member
                content_type = response.headers['Content-Type'].lower()
                extension = IMAGE_TYPES.get(content_type)
                content = response.content
            else:
                msg = 'Failed to download image for program [%s] from [%s]! Response was [%d]:\n%s'
                logger.error(msg, program.title, image_url, response.status_code, response.content)
                return False

        if extension:
            filename = '{uuid}.{extension}'.format(uuid=str(program.uuid), extension=extension)
            # TODO: Get field from _meta.get_field. Tried that approach initially but was getting
            # field save errors for some reasons.
            if data_field == 'image':
                program.card_image.save(filename, ContentFile(content))
            elif data_field == 'organization_logo_override':
                program.organization_logo_override.save(filename, ContentFile(content))
            logger.info('Image for program [%s] successfully updated.', program.title)
            return True
        else:
            msg = 'Image retrieved for program [%s] from [%s] has an unknown content type [%s] and will not be saved.'
            logger.error(msg, program.title, image_url, content_type)

    except Exception:  # pylint: disable=broad-except
        logger.exception('An unknown exception occurred while downloading image for program [%s]', program.title)
    return False


def transform_skills_data(skills_data):
    """
    Utility method to transform the representation of skills data coming-in from Taxonomy-connector.

    * FROM:
         [
            {
                'name': 'Skill 1',
                'description': 'Skill 1',
                'category': {
                'name': 'Category 1'
                },
                'subcategory': {
                    'name': 'Subcategory 1',
                    'category': {
                        'name': 'Category 1'
                    },
                }
            },
            {
                'name': 'Skill 2',
                'description': 'Skill 2',
                'category': {
                'name': 'Category 1'
                    },
                'subcategory': {
                    'name': 'Subcategory 1',
                    'category': {
                        'name': 'Category 1'
                    },
                }
            }
        ]

    * TO:
        [
            {
            'skill': 'Skill 1',
            'category': 'Category 1',
            'subcategory': 'Subcategory 1',
            },
            {
            'skill': 'Skill 2',
            'category': 'Category 1',
            'subcategory': 'Subcategory 1',
            }
        ]
    """
    skills = []
    for skill in skills_data:
        skill_dict = {
            'skill': skill['name'],
            'category': skill['category']['name'] if skill['category'] is not None else '',
            'subcategory': skill['subcategory']['name'] if skill['subcategory'] is not None else ''
        }
        skills.append(skill_dict)
    return skills


def fetch_getsmarter_products():
    """ Returns the products details from the getsmarter API """
    products = []
    getsmarter_api_client = GetSmarterEnterpriseApiClient(
        client_id=settings.GETSMARTER_CLIENT_CREDENTIALS['CLIENT_ID'],
        client_secret=settings.GETSMARTER_CLIENT_CREDENTIALS['CLIENT_SECRET'],
        provider_url=settings.GETSMARTER_CLIENT_CREDENTIALS['PROVIDER_URL'],
        api_url=settings.GETSMARTER_CLIENT_CREDENTIALS['API_URL']
    )
    try:
        response = getsmarter_api_client.request(method='GET',
                                                 url=f"{settings.GETSMARTER_CLIENT_CREDENTIALS['PRODUCTS_DETAILS_URL']}?detail=2")  # pylint: disable=line-too-long
        response.raise_for_status()
        response = response.json()

        if 'products' in response:
            logger.info(f"Products found in API response: {len(response)}")
            products = response['products']
            return products
        else:
            logger.info(f"No products found in API response: {len(response)}")

    except Exception as ex:  # pylint: disable=broad-except
        logger.error(f"Failed to retrieve products from getsmarter API: {ex}")
    return products


def data_modified_timestamp_update(sender, instance, **kwargs):  # pylint: disable=unused-argument
    """
    Receiver function to trigger update data modified timestamp on Course or Program
    from one of their related models in reverse(ForeignKey or M2M).

    This wrapper expects the following two things on a model instance:
     * Field tracker
     * A method called update_product_data_modified_stamp which will be implemented by each model
     depending upon its relation with Course/Program.
    """
    if hasattr(instance, 'field_tracker') and hasattr(instance, 'update_product_data_modified_timestamp'):
        instance.update_product_data_modified_timestamp()


def is_valid_slug_format(val):
    """
    Checks whether a given value follows the slug format, taking into account the selected slug format based on the
    'IS_SUBDIRECTORY_SLUG_FORMAT_ENABLED' waffle toggle value.

    Args:
        val: value to be checked

    Returns:
        True if value follow the slug format else False
    """
    if IS_SUBDIRECTORY_SLUG_FORMAT_ENABLED.is_enabled():
        valid_slug_pattern = SUBDIRECTORY_SLUG_FORMAT_REGEX
    else:
        valid_slug_pattern = SLUG_FORMAT_REGEX
    return bool(re.match(valid_slug_pattern, val))


def is_ocm_course(course):
    """
    Checks whether a given course is an OCM or not

    Args:
        course: a course instance

    Returns:
        True for all edx courses other than exec-ed and bootcamps
    """
    # to avoid circular dependency
    from course_discovery.apps.course_metadata.models import CourseType  # pylint: disable=import-outside-toplevel

    non_ocm_types = [CourseType.EXECUTIVE_EDUCATION_2U, CourseType.BOOTCAMP_2U]
    is_ocm_course_type = course.type.slug not in non_ocm_types
    is_default_product_source = course.product_source.slug == settings.DEFAULT_PRODUCT_SOURCE_SLUG
    return is_ocm_course_type and is_default_product_source


def get_slug_for_course(course):
    """
    Given a course it will return slug and error if there is any'

    Arguments:
          course: course object

    Returns:
        slug: slug in the format 'learn/<primary_subject>/<organization_name>-<course_title>' for open courses and
        'executive-education/<course_title> for executive_education courses'
        error: error while creating slug in the required format
    """
    # to avoid circular dependency
    from course_discovery.apps.course_metadata.models import CourseType  # pylint: disable=import-outside-toplevel
    error = None

    organizations = course.authoring_organizations.all()
    if not organizations:
        error = f"Course with uuid {course.uuid} and title {course.title} does not have any authoring organizations"
        logger.info(error)
        return None, error
    organization_slug = slugify(organizations[0].name.replace('\'', ''))

    def create_slug_for_exec_ed():
        """
        Method to create subdirectory url slug for executive education courses
        """
        course_slug = slugify(course.title)
        slug = f"executive-education/{organization_slug}-{course_slug}"
        if is_existing_slug(slug, course):
            logger.info(f"Slug '{slug}' already exists in DB, recreating slug by adding a number in course_title")
            course_slug = f"{slugify(course.title)}-{get_existing_slug_count(slug) + 1}"
            slug = f"executive-education/{organization_slug}-{course_slug}"
        return slug, error

    def create_slug_for_bootcamps():
        """
        Method to create subdirectory url slug for bootcamps
        """
        course_slug = slugify(course.title)
        course_subjects = course.subjects.all()
        if not course_subjects:
            error = f"Bootcamp with uuid {course.uuid} and title {course.title} does not have any subject"
            logger.info(error)
            return None, error
        primary_subject_slug = course_subjects[0].slug
        organization_short_code = course.organization_short_code_override or organization_slug

        slug = f'boot-camps/{primary_subject_slug}/{organization_short_code}-{course_slug}'
        if is_existing_slug(slug, course):
            logger.info(
                f"Bootcamp Slug '{slug}' already exists in DB, recreating slug by adding a number in course_title"
            )
            course_slug = f"{slugify(course.title)}-{get_existing_slug_count(slug) + 1}"
            slug = f"boot-camps/{primary_subject_slug}/{organization_short_code}-{course_slug}"
        return slug, None

    def create_slug_for_ocm():
        """
        Method to create subdirectory url slug for OCM courses
        """
        course_subjects = course.subjects.all()
        if not course_subjects:
            error = f"Course with uuid {course.uuid} and title {course.title} does not have any subject"
            logger.info(error)
            return None, error

        primary_subject_slug = course_subjects[0].slug
        course_slug = course.active_url_slug

        # course slug is None for courses which are created from studio
        if not course_slug:
            course_slug = slugify(course.title)
            slug = f"learn/{primary_subject_slug}/{organization_slug}-{course_slug}"
            if is_existing_slug(slug, course):
                logger.info(f"Slug '{slug}' already exists in DB, recreating slug by adding a number in course_title")
                course_slug = f"{course.title}-{get_existing_slug_count(slug) + 1}"
        slug = f"learn/{primary_subject_slug}/{organization_slug}-{course_slug}"
        return slug, None

    if course.type.slug == CourseType.BOOTCAMP_2U:
        return create_slug_for_bootcamps()

    if course.type.slug == CourseType.EXECUTIVE_EDUCATION_2U:
        return create_slug_for_exec_ed()

    return create_slug_for_ocm()


def is_existing_slug(slug, course):
    """
    Given a slug and course it check if that slug exists for any other course in DB or not
    """
    # to avoid circular dependency
    from course_discovery.apps.course_metadata.models import CourseUrlSlug  # pylint: disable=import-outside-toplevel
    all_course_historical_slugs_excluding_current = CourseUrlSlug.objects.filter(
        url_slug=slug, partner=course.partner).exclude(course__uuid=course.uuid)
    return all_course_historical_slugs_excluding_current.exists()


def get_existing_slug_count(slug):
    """
    Given a slug it will return count of CourseUrlSlugs objects which is starting from it
    """
    # to avoid circular dependency
    from course_discovery.apps.course_metadata.models import CourseUrlSlug  # pylint: disable=import-outside-toplevel
    return CourseUrlSlug.objects.filter(url_slug__startswith=slug).count()


def is_valid_uuid(val):
    """
    Given a value it will check if value is valid uuid or not
    """
    try:
        uuid.UUID(str(val))
        return True
    except ValueError:
        return False


def validate_slug_format(url_slug, course):
    """
    Given a url_slug and course it will check if url_slug is valid or not based on
    subdirectory_slug_flag and course_run_statuses

    Args:
        url_slug: url_slug to be validated
        course: course object

    Returns:
        none if url_slug is valid else throws ValidationError
    """
    slug_pattern = None

    DEFAULT_SLUG_PATTERN = {
        'slug_format': SLUG_FORMAT_REGEX,
        'error_msg': DEFAULT_SLUG_FORMAT_ERROR_MSG,
    }

    if IS_SUBDIRECTORY_SLUG_FORMAT_ENABLED.is_enabled():
        product_source = course.product_source.slug if course.product_source else None
        product_source_product_type_url_slugs_dict = settings.COURSE_URL_SLUGS_PATTERN.get(product_source, {})
        slug_pattern = product_source_product_type_url_slugs_dict.get(
            course.type.slug,
            product_source_product_type_url_slugs_dict.get('default', DEFAULT_SLUG_PATTERN)
        )
    else:
        slug_pattern = DEFAULT_SLUG_PATTERN

    if not re.match(slug_pattern['slug_format'], url_slug):
        raise ValidationError(slug_pattern['error_msg'].format(url_slug=url_slug))


def transform_dict_keys(data):
    """
    Given a data dictionary, return a new dict that has its keys transformed to
    snake case. For example, Enrollment Track becomes enrollment_track.
    Each key is stripped of whitespaces around the edges, converted to lower case,
    and has internal spaces converted to _. This convention removes the dependency on CSV
    headers format(Enrollment Track vs Enrollment track) and makes code flexible to ignore
    any case sensitivity, among other things.
    """
    transformed_dict = {}
    for key, value in data.items():
        updated_key = key.strip().lower().replace(' ', '_')
        transformed_dict[updated_key] = value

    return transformed_dict
