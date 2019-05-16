import random
import string
import uuid

import requests
from django.utils.functional import cached_property
from django.utils.translation import ugettext as _
from opaque_keys.edx.locator import CourseLocator
from slugify import slugify
from stdimage.models import StdImageFieldFile
from stdimage.utils import UploadTo

from course_discovery.apps.course_metadata.exceptions import MarketingSiteAPIClientException

RESERVED_ELASTICSEARCH_QUERY_OPERATORS = ('AND', 'OR', 'NOT', 'TO',)


def clean_query(query):
    """ Prepares a raw query for search.

    Args:
        query (str): query to clean.

    Returns:
        str: cleaned query
    """
    # Ensure the query is lowercase, since that is how we index our data.
    query = query.lower()

    # Specifying a SearchQuerySet filter will append an explicit AND clause to the query, thus changing its semantics.
    # So we wrap parentheses around the original query in order to preserve the semantics.
    query = '({qs})'.format(qs=query)

    # Ensure all operators are uppercase
    for operator in RESERVED_ELASTICSEARCH_QUERY_OPERATORS:
        old = ' {0} '.format(operator.lower())
        new = ' {0} '.format(operator.upper())
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
                getattr(official_obj, field.name).add(*list(getattr(draft_version, field.name).all()))

    else:
        official_obj = obj

    # Now set fields we were told to
    if attrs:
        for key, value in attrs.items():
            setattr(official_obj, key, value)

    official_obj.save(**save_kwargs)
    return official_obj


def set_draft_state(obj, model, attrs=None):
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
    original_obj = model.objects.get(pk=obj.pk)
    obj.pk = None
    obj.draft = True

    # Now set fields we were told to
    if attrs:
        for key, value in attrs.items():
            setattr(obj, key, value)

    # Will throw an integrity error if the draft row already exists, but this
    # should be caught as part of a try catch in the API calling ensure_draft_world
    obj.save()

    original_obj.draft_version = obj
    original_obj.save()

    # Copy many-to-many fields manually (they are not copied by the pk=None trick above).
    # This must be done after the save() because we need an id.
    for field in model._meta.get_fields():
        if field.many_to_many and not field.auto_created:
            getattr(obj, field.name).add(*list(getattr(original_obj, field.name).all()))

    return obj, original_obj


def ensure_draft_world(obj):
    """
    Ensures the draft world exists for an object. The draft world is defined as all draft objects related to
    the incoming draft object. For now, this will create the draft Course, all draft Course Runs associated
    with that course, all draft Seats associated with all of the course runs, and all draft Entitlements
    associated with the course.

    Assumes that if the given object is already a draft, the draft world for that object already exists.

    Will throw an integrity error if the draft row already exists, but this
    should be caught as part of a try catch in the API calling ensure_draft_world

    Parameters:
        obj (Model object): The object to create a draft state for. *Must have draft as an attribute.*

    Returns:
        obj (Model object): The returned object will be the draft version on the input object.
    """
    from course_discovery.apps.course_metadata.models import Course, CourseEntitlement, CourseRun, Seat
    if obj.draft:
        return obj

    if isinstance(obj, CourseRun):
        ensure_draft_world(obj.course)
        return CourseRun.everything.get(key=obj.key, draft=True)

    elif isinstance(obj, Course):
        # We need to null this out because it will fail with a OneToOne uniqueness error when saving the draft
        obj.canonical_course_run = None
        draft_course, original_course = set_draft_state(obj, Course)
        draft_course.slug = original_course.slug

        # Create draft course runs, the corresponding draft seats, and the draft entitlement
        for run in original_course.course_runs.all():
            draft_run, original_run = set_draft_state(run, CourseRun, {'course': draft_course})
            draft_run.slug = original_run.slug
            draft_run.save()

            for seat in original_run.seats.all():
                set_draft_state(seat, Seat, {'course_run': draft_run})
            if original_course.canonical_course_run and draft_run.uuid == original_course.canonical_course_run.uuid:
                draft_course.canonical_course_run = draft_run
        for entitlement in original_course.entitlements.all():
            set_draft_state(entitlement, CourseEntitlement, {'course': draft_course})

        draft_course.save()
        return draft_course
    else:
        raise Exception('Ensure draft world only accepts Courses and Course Runs.')


class UploadToFieldNamePath(UploadTo):
    """
    This is a utility to create file path for uploads based on instance field value
    """
    def __init__(self, populate_from, **kwargs):
        self.populate_from = populate_from
        super(UploadToFieldNamePath, self).__init__(populate_from, **kwargs)

    def __call__(self, instance, filename):
        field_value = getattr(instance, self.populate_from)
        # Update name with Random string of 12 character at the end example '-ba123cd89e97'
        self.kwargs.update({
            'name': str(field_value) + str(uuid.uuid4())[23:]
        })
        return super(UploadToFieldNamePath, self).__call__(instance, filename)


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


def uslugify(string):
    """Slugifies a string, while handling unicode"""
    # only_ascii=True asks slugify to convert unicode to ascii
    slug = slugify(string, only_ascii=True)

    # Version 0.1.3 of unicode-slugify does not do the following for us.
    # But 0.1.4 does! So once it's available and we upgrade, we can drop this extra logic.
    slug = slug.strip().replace(' ', '-').lower()
    slug = ''.join(filter(lambda c: c.isalnum() or c in '-_~', slug))
    # End code that can be dropped with 0.1.4

    return slug


def parse_course_key_fragment(fragment):
    """
    Parses a course key fragment like "edX+DemoX" or "edX/DemoX" into org and course number. We call this a fragment,
    because this kind of "course key" is not to be confused with the CourseKey class that parses a full course run key
    like "course-v1:edX+DemoX+1T2019".

    Returns a two values: (org, course number). If the key could not be parsed, then ValueError is raised.
    """
    split = fragment.split('/') if '/' in fragment else fragment.split('+')
    if len(split) != 2:
        raise ValueError('Could not understand course key fragment "{}".'.format(fragment))
    return split[0], split[1]


def validate_course_number(course_number):
    """
    Verifies that the Course Number does not contain invalid characters. Raises a ValueError if there are
    invalid characters.

    Args:
        course_number: Course Number String
    """
    if not CourseLocator.ALLOWED_ID_RE.match(course_number):
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


class MarketingSiteAPIClient(object):
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
        login_url = '{root}/user'.format(root=self.api_url)
        login_data = {
            'name': self.username,
            'pass': self.password,
            'form_id': 'user_login',
            'op': 'Log in',
        }
        response = session.post(login_url, data=login_data)
        admin_url = '{root}/admin'.format(root=self.api_url)
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
        token_url = '{root}/restws/session/token?cachebust={qs}'.format(root=self.api_url, qs=random_qs)
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
        user_url = '{root}/user.json?name={username}'.format(root=self.api_url, username=self.username)
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
