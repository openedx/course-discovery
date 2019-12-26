import logging

from django.contrib.auth.models import Group
from django.db import models
from django.utils.functional import cached_property
from django.utils.translation import ugettext_lazy as _
from django_extensions.db.fields import AutoSlugField
from django_extensions.db.models import TimeStampedModel
from django_fsm import FSMField
from simple_history.models import HistoricalRecords
from sortedm2m.fields import SortedManyToManyField
from stdimage.models import StdImageField
from taggit.managers import TaggableManager

from course_discovery.apps.core.models import Currency, User
from course_discovery.apps.course_metadata.choices import CourseRunPacing
from course_discovery.apps.course_metadata.models import LevelType, Organization, Person, Subject
from course_discovery.apps.course_metadata.utils import UploadToFieldNamePath, uslugify
from course_discovery.apps.ietf_language_tags.models import LanguageTag
from course_discovery.apps.publisher.choices import (
    CourseRunStateChoices, CourseStateChoices, InternalUserRole, PublisherUserRole
)
from course_discovery.apps.publisher.validators import ImageMultiSizeValidator

logger = logging.getLogger(__name__)


class ChangedByMixin(models.Model):
    changed_by = models.ForeignKey(User, models.CASCADE, null=True, blank=True)

    class Meta:
        abstract = True


class Course(TimeStampedModel, ChangedByMixin):
    """ Publisher Course model. It contains fields related to the course intake form."""

    # Versions for code paths in publisher Course and Course Run Create/Edit
    # Is the original version for courses without Entitlements (No mode/price set at Course level)
    SEAT_VERSION = 0
    # Is the version for Courses that have a mode and price set (a CourseEntitlement), where all course runs must match
    ENTITLEMENT_VERSION = 1

    title = models.CharField(max_length=255, default=None, null=True, blank=True, verbose_name='Course title')
    number = models.CharField(max_length=50, null=True, blank=True, verbose_name='Course number')
    short_description = models.TextField(default=None, null=True, blank=True, verbose_name='Brief Description')
    full_description = models.TextField(default=None, null=True, blank=True, verbose_name='Full Description')
    organizations = models.ManyToManyField(
        Organization, blank=True, related_name='publisher_courses', verbose_name='Partner Name'
    )
    level_type = models.ForeignKey(
        LevelType, models.CASCADE, default=None, null=True, blank=True, related_name='publisher_courses',
        verbose_name='Level Type',
    )
    expected_learnings = models.TextField(default=None, null=True, blank=True, verbose_name="Expected Learnings")
    syllabus = models.TextField(default=None, null=True, blank=True)
    prerequisites = models.TextField(default=None, null=True, blank=True, verbose_name='Prerequisites')
    learner_testimonial = models.TextField(default=None, null=True, blank=True, verbose_name='Learner Testimonials')
    additional_information = models.TextField(
        default=None, null=True, blank=True, verbose_name='Additional Information'
    )
    primary_subject = models.ForeignKey(
        Subject, models.CASCADE, default=None, null=True, blank=True, related_name='publisher_courses_primary',
    )
    secondary_subject = models.ForeignKey(
        Subject, models.CASCADE, default=None, null=True, blank=True, related_name='publisher_courses_secondary',
    )
    tertiary_subject = models.ForeignKey(
        Subject, models.CASCADE, default=None, null=True, blank=True, related_name='publisher_courses_tertiary',
    )

    image = StdImageField(
        upload_to=UploadToFieldNamePath(
            populate_from='number',
            path='media/publisher/courses/images'
        ),
        blank=True,
        null=True,
        validators=[ImageMultiSizeValidator([(2120, 1192), (378, 225)], preferred_size=(1134, 675))]
    )

    is_seo_review = models.BooleanField(default=False)
    keywords = TaggableManager(blank=True, verbose_name='keywords')
    faq = models.TextField(default=None, null=True, blank=True, verbose_name='FAQ')
    video_link = models.URLField(default=None, null=True, blank=True, verbose_name='Video Link')
    version = models.IntegerField(default=SEAT_VERSION, verbose_name='Workflow Version')

    # temp fields for data migrations only.
    course_metadata_pk = models.PositiveIntegerField(null=True, blank=True, verbose_name='Course Metadata Course PK')
    url_slug = AutoSlugField(populate_from='title', editable=True, slugify_function=uslugify, overwrite_on_add=False,
                             help_text='Leave this field blank to have the value generated automatically.',
                             unique=True)

    history = HistoricalRecords(excluded_fields=['url_slug'])

    def __str__(self):
        return self.title

    class Meta(TimeStampedModel.Meta):
        permissions = (
            ('view_course', 'Can view course'),
        )

    @cached_property
    def key(self):
        return '{org}+{number}'.format(org=self.organizations.first().key, number=self.number)


class CourseRun(TimeStampedModel, ChangedByMixin):
    """ Publisher CourseRun model. It contains fields related to the course run intake form."""
    PRIORITY_LEVEL_1 = 'L1'
    PRIORITY_LEVEL_2 = 'L2'
    PRIORITY_LEVEL_3 = 'L3'
    PRIORITY_LEVEL_4 = 'L4'
    PRIORITY_LEVEL_5 = 'L5'

    PRIORITY_LEVELS = (
        (PRIORITY_LEVEL_1, 'Level 1'),
        (PRIORITY_LEVEL_2, 'Level 2'),
        (PRIORITY_LEVEL_3, 'Level 3'),
        (PRIORITY_LEVEL_4, 'Level 4'),
        (PRIORITY_LEVEL_5, 'Level 5'),
    )

    DEFAULT_PACING_TYPE = CourseRunPacing.Instructor

    course = models.ForeignKey(Course, models.CASCADE, related_name='publisher_course_runs')
    lms_course_id = models.CharField(max_length=255, unique=True, null=True, blank=True)
    external_key = models.CharField(max_length=225, blank=True, null=True)

    start = models.DateTimeField(null=True, blank=True)
    end = models.DateTimeField(null=True, blank=True)
    certificate_generation = models.DateTimeField(null=True, blank=True)
    pacing_type = models.CharField(
        max_length=255, db_index=True, null=True, blank=True, choices=CourseRunPacing.choices,
        validators=[CourseRunPacing.validator], default=DEFAULT_PACING_TYPE
    )
    staff = SortedManyToManyField(Person, blank=True, related_name='publisher_course_runs_staffed')
    min_effort = models.PositiveSmallIntegerField(
        null=True, blank=True,
        help_text='Estimated minimum number of hours per week needed to complete a course run.')
    max_effort = models.PositiveSmallIntegerField(
        null=True, blank=True,
        help_text='Estimated maximum number of hours per week needed to complete a course run.')
    language = models.ForeignKey(
        LanguageTag, models.CASCADE, null=True, blank=True,
        related_name='publisher_course_runs', verbose_name='Content Language'
    )
    transcript_languages = models.ManyToManyField(
        LanguageTag, blank=True, related_name='publisher_transcript_course_runs'
    )
    length = models.PositiveIntegerField(
        null=True, blank=True, help_text='Length of course, in number of weeks'
    )
    sponsor = models.ManyToManyField(Organization, blank=True, related_name='publisher_course_runs')

    is_re_run = models.BooleanField(default=False)
    is_xseries = models.BooleanField(default=False)
    xseries_name = models.CharField(max_length=255, null=True, blank=True)
    is_micromasters = models.BooleanField(default=False)
    micromasters_name = models.CharField(max_length=255, null=True, blank=True)
    is_professional_certificate = models.BooleanField(default=False)
    professional_certificate_name = models.CharField(max_length=255, null=True, blank=True)
    contacted_partner_manager = models.BooleanField(default=False)

    notes = models.TextField(
        default=None, null=True, blank=True,
        help_text='Please add any additional notes or special instructions for the course About Page.'
    )
    target_content = models.BooleanField(default=False)
    priority = models.CharField(
        max_length=5, choices=PRIORITY_LEVELS, null=True, blank=True
    )
    course_team_admins = models.TextField(
        default=None, blank=True, null=True, help_text='Comma separated list of edX usernames or emails of admins.'
    )
    course_team_additional_staff = models.TextField(
        default=None, blank=True, null=True,
        help_text='Comma separated list of edX usernames or emails of additional staff.'
    )
    video_language = models.ForeignKey(LanguageTag, models.CASCADE, null=True, blank=True,
                                       related_name='video_language')

    # temporary field to save the canonical course run image. In 2nd script this url field
    # will be used to download the image and save into course model --> course image.
    card_image_url = models.URLField(null=True, blank=True, verbose_name='canonical course run image')

    short_description_override = models.TextField(
        default=None, null=True, blank=True,
        help_text=(
            "Short description specific for this run of a course. Leave this value blank to default to "
            "the parent course's short_description attribute."))

    title_override = models.CharField(
        max_length=255, default=None, null=True, blank=True,
        help_text=(
            "Title specific for this run of a course. Leave this value blank to default to the parent course's title."))

    full_description_override = models.TextField(
        default=None, null=True, blank=True,
        help_text=(
            "Full description specific for this run of a course. Leave this value blank to default to "
            "the parent course's full_description attribute."))

    has_ofac_restrictions = models.BooleanField(
        default=False,
        verbose_name='Has OFAC Restriction Text'
    )

    history = HistoricalRecords()

    def __str__(self):
        return '{course}: {start_date}'.format(course=self.course.title, start_date=self.start)


class Seat(TimeStampedModel, ChangedByMixin):
    HONOR = 'honor'
    AUDIT = 'audit'
    VERIFIED = 'verified'
    PROFESSIONAL = 'professional'
    NO_ID_PROFESSIONAL = 'no-id-professional'
    CREDIT = 'credit'

    SEAT_TYPE_CHOICES = (
        (HONOR, 'Honor'),
        (AUDIT, 'Audit'),
        (VERIFIED, 'Verified'),
        (PROFESSIONAL, 'Professional (with ID verification)'),
        (NO_ID_PROFESSIONAL, 'Professional (no ID verification)'),
        (CREDIT, 'Credit'),
    )

    PRICE_FIELD_CONFIG = {
        'decimal_places': 2,
        'max_digits': 10,
        'null': False,
        'default': 0.00,
    }
    course_run = models.ForeignKey(CourseRun, models.CASCADE, related_name='seats')
    type = models.CharField(max_length=63, choices=SEAT_TYPE_CHOICES, verbose_name='Seat type')
    price = models.DecimalField(**PRICE_FIELD_CONFIG)
    currency = models.ForeignKey(Currency, models.CASCADE, default='USD', related_name='publisher_seats')
    upgrade_deadline = models.DateTimeField(null=True, blank=True)
    credit_provider = models.CharField(max_length=255, null=True, blank=True)
    credit_hours = models.IntegerField(null=True, blank=True)
    credit_price = models.DecimalField(**PRICE_FIELD_CONFIG)
    masters_track = models.BooleanField(default=False)

    history = HistoricalRecords()

    def __str__(self):
        return '{course}: {type}'.format(course=self.course_run.course.title, type=self.type)


class CourseEntitlement(TimeStampedModel):
    VERIFIED = 'verified'
    PROFESSIONAL = 'professional'

    COURSE_MODE_CHOICES = (
        (VERIFIED, 'Verified'),
        (PROFESSIONAL, 'Professional'),
    )

    PRICE_FIELD_CONFIG = {
        'decimal_places': 2,
        'max_digits': 10,
        'null': False,
        'default': 0.00,
    }

    course = models.ForeignKey(Course, models.CASCADE, related_name='entitlements')
    mode = models.CharField(max_length=63, choices=COURSE_MODE_CHOICES, verbose_name='Course mode')
    price = models.DecimalField(**PRICE_FIELD_CONFIG)
    currency = models.ForeignKey(Currency, models.CASCADE, default='USD', related_name='publisher_entitlements')

    class Meta:
        unique_together = (
            ('course', 'mode')
        )


class UserAttributes(TimeStampedModel):
    """ Record additional metadata about a user. """
    user = models.OneToOneField(User, models.CASCADE, related_name='attributes')
    enable_email_notification = models.BooleanField(default=True)

    def __str__(self):
        return '{user}: {email_notification}'.format(
            user=self.user, email_notification=self.enable_email_notification
        )

    class Meta:
        verbose_name_plural = 'UserAttributes'


class OrganizationUserRole(TimeStampedModel):
    """ User Roles model for Organization. """

    organization = models.ForeignKey(Organization, models.CASCADE, related_name='organization_user_roles')
    user = models.ForeignKey(User, models.CASCADE, related_name='organization_user_roles')
    role = models.CharField(
        max_length=63, choices=InternalUserRole.choices, verbose_name=_('Organization Role')
    )

    history = HistoricalRecords()

    class Meta:
        unique_together = (
            ('organization', 'user', 'role'),
        )

    def __str__(self):
        return '{organization}: {user}: {role}'.format(
            organization=self.organization,
            user=self.user,
            role=self.role
        )


class CourseUserRole(TimeStampedModel, ChangedByMixin):
    """ User Course Roles model. """
    course = models.ForeignKey(Course, models.CASCADE, related_name='course_user_roles')
    user = models.ForeignKey(User, models.CASCADE, related_name='course_user_roles')
    role = models.CharField(
        max_length=63, choices=PublisherUserRole.choices, verbose_name='Course Role'
    )

    history = HistoricalRecords()

    class Meta:
        unique_together = (
            ('course', 'user', 'role'),
        )

    def __str__(self):
        return '{course}: {user}: {role}'.format(
            course=self.course,
            user=self.user,
            role=self.role
        )


class OrganizationExtension(TimeStampedModel):
    """ Organization-Extension relation model. """
    EDIT_COURSE = 'publisher_edit_course'
    EDIT_COURSE_RUN = 'publisher_edit_course_run'
    VIEW_COURSE = 'publisher_view_course'
    VIEW_COURSE_RUN = 'publisher_view_course_run'

    organization = models.OneToOneField(Organization, models.CASCADE, related_name='organization_extension')
    group = models.OneToOneField(Group, models.CASCADE, related_name='organization_extension')

    history = HistoricalRecords()

    class Meta(TimeStampedModel.Meta):
        permissions = (
            ('publisher_edit_course', 'Can edit course'),
            ('publisher_edit_course_run', 'Can edit course run'),
            ('publisher_view_course', 'Can view course'),
            ('publisher_view_course_run', 'Can view the course run'),
        )

    def __str__(self):
        return '{organization}: {group}'.format(
            organization=self.organization, group=self.group
        )


class CourseState(TimeStampedModel, ChangedByMixin):
    """ Publisher Workflow Course State Model. """

    name = FSMField(default=CourseStateChoices.Draft, choices=CourseStateChoices.choices)
    approved_by_role = models.CharField(blank=True, null=True, max_length=63, choices=PublisherUserRole.choices)
    owner_role = models.CharField(max_length=63, choices=PublisherUserRole.choices)
    course = models.OneToOneField(Course, models.CASCADE, related_name='course_state')
    owner_role_modified = models.DateTimeField(auto_now_add=True, null=True, blank=True)
    marketing_reviewed = models.BooleanField(default=False)

    history = HistoricalRecords()

    def __str__(self):
        return self.get_name_display()


class CourseRunState(TimeStampedModel, ChangedByMixin):
    """ Publisher Workflow Course Run State Model. """

    name = FSMField(default=CourseRunStateChoices.Draft, choices=CourseRunStateChoices.choices)
    approved_by_role = models.CharField(blank=True, null=True, max_length=63, choices=PublisherUserRole.choices)
    owner_role = models.CharField(max_length=63, choices=PublisherUserRole.choices)
    course_run = models.OneToOneField(CourseRun, models.CASCADE, related_name='course_run_state')
    owner_role_modified = models.DateTimeField(auto_now_add=True, null=True, blank=True)
    preview_accepted = models.BooleanField(default=False)

    history = HistoricalRecords()

    def __str__(self):
        return self.get_name_display()


class PublisherUser(User):
    """ Publisher User Proxy Model. """

    class Meta:
        proxy = True
