import datetime
import logging
from urllib.parse import urljoin

import pytz
import waffle
from django.conf import settings
from django.contrib.auth.models import Group
from django.core.exceptions import ObjectDoesNotExist
from django.db import models
from django.urls import reverse
from django.utils import timezone
from django.utils.functional import cached_property
from django.utils.translation import ugettext_lazy as _
from django_extensions.db.models import TimeStampedModel
from django_fsm import FSMField, transition
from guardian.shortcuts import get_objects_for_user
from simple_history.models import HistoricalRecords
from solo.models import SingletonModel
from sortedm2m.fields import SortedManyToManyField
from stdimage.models import StdImageField
from taggit.managers import TaggableManager

from course_discovery.apps.core.models import Currency, User
from course_discovery.apps.course_metadata.choices import CourseRunPacing, CourseRunStatus
from course_discovery.apps.course_metadata.models import Course as DiscoveryCourse
from course_discovery.apps.course_metadata.models import CourseRun as DiscoveryCourseRun
from course_discovery.apps.course_metadata.models import LevelType, Organization, Person, Subject
from course_discovery.apps.course_metadata.publishers import CourseRunMarketingSitePublisher
from course_discovery.apps.course_metadata.utils import UploadToFieldNamePath
from course_discovery.apps.ietf_language_tags.models import LanguageTag
from course_discovery.apps.publisher import emails
from course_discovery.apps.publisher.choices import (
    CourseRunStateChoices, CourseStateChoices, InternalUserRole, PublisherUserRole
)
from course_discovery.apps.publisher.constants import PUBLISHER_ENABLE_READ_ONLY_FIELDS
from course_discovery.apps.publisher.exceptions import CourseRunEditException
from course_discovery.apps.publisher.utils import is_email_notification_enabled, is_internal_user, is_publisher_admin
from course_discovery.apps.publisher.validators import ImageMultiSizeValidator

logger = logging.getLogger(__name__)


class ChangedByMixin(models.Model):
    changed_by = models.ForeignKey(User, null=True, blank=True)

    class Meta:
        abstract = True


class Course(TimeStampedModel, ChangedByMixin):
    """ Publisher Course model. It contains fields related to the course intake form."""

    # Versions for code paths in publisher Course and Course Run Create/Edit
    # Is the original version for courses without Entitlements (No mode/price set at Course level)
    SEAT_VERSION = 0
    # Is the version for Courses that have a mode and price set (a CourseEntitlement), where all course runs must match
    ENTITLEMENT_VERSION = 1

    title = models.CharField(max_length=255, default=None, null=True, blank=True, verbose_name=_('Course title'))
    number = models.CharField(max_length=50, null=True, blank=True, verbose_name=_('Course number'))
    short_description = models.TextField(
        default=None, null=True, blank=True, verbose_name=_('Brief Description')
    )
    full_description = models.TextField(default=None, null=True, blank=True, verbose_name=_('Full Description'))
    organizations = models.ManyToManyField(
        Organization, blank=True, related_name='publisher_courses', verbose_name=_('Partner Name')
    )
    level_type = models.ForeignKey(
        LevelType, default=None, null=True, blank=True, related_name='publisher_courses', verbose_name=_('Level Type')
    )
    expected_learnings = models.TextField(default=None, null=True, blank=True, verbose_name=_("Expected Learnings"))
    syllabus = models.TextField(default=None, null=True, blank=True)
    prerequisites = models.TextField(default=None, null=True, blank=True, verbose_name=_('Prerequisites'))
    learner_testimonial = models.TextField(default=None, null=True, blank=True, verbose_name=_('Learner Testimonials'))
    additional_information = models.TextField(
        default=None, null=True, blank=True, verbose_name=_('Additional Information')
    )
    primary_subject = models.ForeignKey(
        Subject, default=None, null=True, blank=True, related_name='publisher_courses_primary'
    )
    secondary_subject = models.ForeignKey(
        Subject, default=None, null=True, blank=True, related_name='publisher_courses_secondary'
    )
    tertiary_subject = models.ForeignKey(
        Subject, default=None, null=True, blank=True, related_name='publisher_courses_tertiary'
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
    faq = models.TextField(default=None, null=True, blank=True, verbose_name=_('FAQ'))
    video_link = models.URLField(default=None, null=True, blank=True, verbose_name=_('Video Link'))
    version = models.IntegerField(default=SEAT_VERSION, verbose_name='Workflow Version')

    has_ofac_restrictions = models.BooleanField(default=False, verbose_name=_('Course Has OFAC Restrictions'))

    # temp fields for data migrations only.
    course_metadata_pk = models.PositiveIntegerField(null=True, blank=True, verbose_name=_('Course Metadata Course PK'))

    history = HistoricalRecords()

    def __str__(self):
        return self.title

    @property
    def uses_entitlements(self):
        """
        Returns a bool indicating whether or not this Course has been configured to use entitlement products.
        """
        return self.version == self.ENTITLEMENT_VERSION

    @property
    def post_back_url(self):
        return reverse('publisher:publisher_courses_edit', kwargs={'pk': self.id})

    class Meta(TimeStampedModel.Meta):
        permissions = (
            ('view_course', 'Can view course'),
        )

    def get_course_users_emails(self):
        """ Returns the list of users emails with enable email notifications
        against a course. By default if attribute value does not exists
        then user will be eligible for emails.
        """
        user_emails = [
            role.user.email for role in self.course_user_roles.all()
            if is_email_notification_enabled(role.user)
        ]

        return user_emails

    def get_user_role(self, user):
        """
        Returns the role of a user in the course if it exists
        """
        try:
            return self.course_user_roles.get(user=user).role
        except CourseUserRole.DoesNotExist:
            return None

    @property
    def organization_name(self):
        """
        Returns organization name for a course.
        """
        organization_name = ''
        try:
            organization_name = self.organizations.only('key').first().key
        except AttributeError:
            pass

        return organization_name

    @property
    def keywords_data(self):
        keywords = self.keywords.all()
        if keywords:
            return ', '.join(k.name for k in keywords)

        return None

    @property
    def project_coordinator(self):
        """
        Return course project coordinator user.
        """
        try:
            return self.course_user_roles.only('user').get(role=PublisherUserRole.ProjectCoordinator).user
        except CourseUserRole.DoesNotExist:
            return None

    def assign_organization_role(self, organization):
        """
        Create course-user-roles except CourseTeam for the given organization against a course.
        """
        for user_role in organization.organization_user_roles.exclude(role=PublisherUserRole.CourseTeam):
            CourseUserRole.add_course_roles(self, user_role.role, user_role.user)

    @property
    def course_runs(self):
        return self.publisher_course_runs.order_by('-created')

    @property
    def course_team_admin(self):
        """
        Return course team user.
        """
        try:
            return self.course_user_roles.get(role=PublisherUserRole.CourseTeam).user
        except CourseUserRole.DoesNotExist:
            return None

    @property
    def partner(self):
        organization = self.organizations.all().first()
        return organization.partner if organization else None

    @property
    def marketing_reviewer(self):
        """
        Return course marketing reviewer user.
        """
        try:
            return self.course_user_roles.get(role=PublisherUserRole.MarketingReviewer).user
        except CourseUserRole.DoesNotExist:
            return None

    @property
    def organization_extension(self):
        organization = self.organizations.all().first()
        if organization:
            return organization.organization_extension

        return None

    @property
    def publisher(self):
        """
        Return course publisher user.
        """
        try:
            return self.course_user_roles.get(role=PublisherUserRole.Publisher).user
        except CourseUserRole.DoesNotExist:
            return None

    @property
    def course_short_description(self):
        course_run = self.course_runs.filter(course_run_state__name=CourseRunStateChoices.Published).first()

        if course_run and course_run.short_description_override:
            return course_run.short_description_override

        return self.short_description

    @property
    def course_full_description(self):
        course_run = self.course_runs.filter(course_run_state__name=CourseRunStateChoices.Published).first()

        if course_run and course_run.full_description_override:
            return course_run.full_description_override

        return self.full_description

    @property
    def course_title(self):
        course_run = self.course_runs.filter(course_run_state__name=CourseRunStateChoices.Published).first()

        if course_run and course_run.title_override:
            return course_run.title_override

        return self.title

    @cached_property
    def discovery_counterpart(self):
        return DiscoveryCourse.objects.get(partner=self.partner, key=self.key)

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
        (PRIORITY_LEVEL_1, _('Level 1')),
        (PRIORITY_LEVEL_2, _('Level 2')),
        (PRIORITY_LEVEL_3, _('Level 3')),
        (PRIORITY_LEVEL_4, _('Level 4')),
        (PRIORITY_LEVEL_5, _('Level 5')),
    )

    DEFAULT_PACING_TYPE = CourseRunPacing.Instructor

    course = models.ForeignKey(Course, related_name='publisher_course_runs')
    lms_course_id = models.CharField(max_length=255, unique=True, null=True, blank=True)

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
        help_text=_('Estimated minimum number of hours per week needed to complete a course run.'))
    max_effort = models.PositiveSmallIntegerField(
        null=True, blank=True,
        help_text=_('Estimated maximum number of hours per week needed to complete a course run.'))
    language = models.ForeignKey(
        LanguageTag, null=True, blank=True,
        related_name='publisher_course_runs', verbose_name=_('Content Language')
    )
    transcript_languages = models.ManyToManyField(
        LanguageTag, blank=True, related_name='publisher_transcript_course_runs'
    )
    length = models.PositiveIntegerField(
        null=True, blank=True, help_text=_("Length of course, in number of weeks")
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
        default=None, null=True, blank=True, help_text=_(
            "Please add any additional notes or special instructions for the course About Page."
        )
    )
    target_content = models.BooleanField(default=False)
    priority = models.CharField(
        max_length=5, choices=PRIORITY_LEVELS, null=True, blank=True
    )
    course_team_admins = models.TextField(
        default=None, blank=True, null=True, help_text=_("Comma separated list of edX usernames or emails of admins.")
    )
    course_team_additional_staff = models.TextField(
        default=None, blank=True, null=True, help_text=_(
            "Comma separated list of edX usernames or emails of additional staff."
        )
    )
    video_language = models.ForeignKey(LanguageTag, null=True, blank=True, related_name='video_language')

    # temporary field to save the canonical course run image. In 2nd script this url field
    # will be used to download the image and save into course model --> course image.
    card_image_url = models.URLField(null=True, blank=True, verbose_name='canonical course run image')

    short_description_override = models.TextField(
        default=None, null=True, blank=True,
        help_text=_(
            "Short description specific for this run of a course. Leave this value blank to default to "
            "the parent course's short_description attribute."))

    title_override = models.CharField(
        max_length=255, default=None, null=True, blank=True,
        help_text=_(
            "Title specific for this run of a course. Leave this value blank to default to the parent course's title."))

    full_description_override = models.TextField(
        default=None, null=True, blank=True,
        help_text=_(
            "Full description specific for this run of a course. Leave this value blank to default to "
            "the parent course's full_description attribute."))

    has_ofac_restrictions = models.BooleanField(
        default=False,
        verbose_name=_('Has OFAC Restriction Text')
    )

    history = HistoricalRecords()

    def __str__(self):
        return '{course}: {start_date}'.format(course=self.course.title, start_date=self.start)

    @property
    def post_back_url(self):
        return reverse('publisher:publisher_course_runs_edit', kwargs={'pk': self.id})

    @property
    def created_by(self):
        history_user = self.history.order_by('history_date').first().history_user  # pylint: disable=no-member
        if history_user:
            return history_user.get_full_name() or history_user.username

        return

    @property
    def preview_url(self):
        run = self.discovery_course_run
        # test staff as a proxy for if discovery has been published to yet - we don't want to show URL until then
        run_valid = run and run.staff.exists()
        return run.marketing_url if run_valid else None

    @property
    def discovery_course_run(self):
        if self.lms_course_id:
            return DiscoveryCourseRun.objects.filter(key=self.lms_course_id).first()
        else:
            return None

    @property
    def studio_url(self):
        if self.lms_course_id and self.course.partner and self.course.partner.studio_url:
            path = 'course/{lms_course_id}'.format(lms_course_id=self.lms_course_id)
            return urljoin(self.course.partner.studio_url, path)

        return None

    @property
    def studio_schedule_and_details_url(self):
        if self.lms_course_id and self.course.partner and self.course.partner.studio_url:
            path = 'settings/details/{lms_course_id}'.format(lms_course_id=self.lms_course_id)
            return urljoin(self.course.partner.studio_url, path)

    @property
    def has_valid_staff(self):
        """ Check that each staff member has his bio data and image."""
        staff_members = self.staff.all()
        if not staff_members:
            return False

        return all([staff.bio and staff.get_profile_image_url for staff in staff_members])

    @property
    def is_valid_micromasters(self):
        """ Check that `micromasters_name` is provided if is_micromaster is True."""
        if not self.is_micromasters:
            return True

        if self.is_micromasters and self.micromasters_name:
            return True

        return False

    @property
    def is_valid_xseries(self):
        """ Check that `xseries_name` is provided if is_xseries is True."""
        if not self.is_xseries:
            return True

        if self.is_xseries and self.xseries_name:
            return True

        return False

    @property
    def is_valid_professional_certificate(self):
        """ Check that `professional_certificate_name` is provided if is_professional_certificate is True."""
        if not self.is_professional_certificate:
            return True

        if self.is_professional_certificate and self.professional_certificate_name:
            return True

        return False

    @property
    def has_valid_seats(self):
        """
        Validate course-run has a  valid seats.
        """
        seats = self.seats.filter(type__in=[Seat.AUDIT, Seat.VERIFIED, Seat.PROFESSIONAL, Seat.CREDIT])
        return all([seat.is_valid_seat for seat in seats]) if seats else False

    @property
    def paid_seats(self):
        """ Return course run paid seats """
        return self.seats.filter(type__in=Seat.PAID_SEATS)

    def get_absolute_url(self):
        return reverse('publisher:publisher_course_run_detail', kwargs={'pk': self.id})

    @cached_property
    def discovery_counterpart_latest_by_start_date(self):
        try:
            discovery_course = self.course.discovery_counterpart
            return discovery_course.course_runs.latest('start')
        except ObjectDoesNotExist:
            logger.info(
                'Related discovery course run not found for [%s] with partner [%s] ',
                self.course.key,
                self.course.partner
            )
            return None

    @cached_property
    def discovery_counterpart(self):
        try:
            discovery_course = self.course.discovery_counterpart
            return discovery_course.course_runs.get(key=self.lms_course_id)
        except ObjectDoesNotExist:
            logger.info(
                'Related discovery course run not found for [%s] with partner [%s] ',
                self.course.key,
                self.course.partner
            )
            return None

    @property
    def pacing_type_temporary(self):
        """
            This property serves as a temporary intermediary in order to support a waffle
            switch that will toggle between the original database backed pacing_type value
            and a new read-only value that is pulled from course_discovery.

            Once the switch is no longer needed, the pacing_type field will be removed,
            and this property will be renamed appropriately.

            The progress of the above work will be tracked in the following ticket:
            https://openedx.atlassian.net/browse/EDUCATOR-3488.
        """
        if waffle.switch_is_active(PUBLISHER_ENABLE_READ_ONLY_FIELDS):
            discovery_counterpart = self.discovery_counterpart

            if discovery_counterpart and discovery_counterpart.pacing_type:
                return discovery_counterpart.pacing_type
            else:
                return self.DEFAULT_PACING_TYPE
        else:
            return self.pacing_type

    @pacing_type_temporary.setter
    def pacing_type_temporary(self, value):
        if waffle.switch_is_active(PUBLISHER_ENABLE_READ_ONLY_FIELDS):
            raise CourseRunEditException
        else:
            # Treat empty strings as NULL
            value = value or None
            self.pacing_type = value

    def get_pacing_type_temporary_display(self):
        if waffle.switch_is_active(PUBLISHER_ENABLE_READ_ONLY_FIELDS):
            discovery_counterpart = self.discovery_counterpart

            if discovery_counterpart and discovery_counterpart.pacing_type:
                return discovery_counterpart.get_pacing_type_display()

            return _('Instructor-paced')

        else:
            return self.get_pacing_type_display()

    @property
    def start_date_temporary(self):
        """
            This property serves as a temporary intermediary in order to support a waffle
            switch that will toggle between the original database backed start value
            and a new read-only value that is pulled from course_discovery.

            The start date will need to continue to exist for the write on create,
            until that functionality is officially moved to Studio creation.

            The progress of the above work will be tracked in the following ticket:
            https://openedx.atlassian.net/browse/EDUCATOR-3524.
        """
        start_date = self.start

        if waffle.switch_is_active(PUBLISHER_ENABLE_READ_ONLY_FIELDS):
            discovery_counterpart = self.discovery_counterpart

            if discovery_counterpart and discovery_counterpart.start:
                start_date = discovery_counterpart.start

        return start_date

    @start_date_temporary.setter
    def start_date_temporary(self, value):
        if waffle.switch_is_active(PUBLISHER_ENABLE_READ_ONLY_FIELDS):
            raise CourseRunEditException
        else:
            self.start = value

    @property
    def end_date_temporary(self):
        """
            This property serves as a temporary intermediary in order to support a waffle
            switch that will toggle between the original database backed end value
            and a new read-only value that is pulled from course_discovery.

            The end date will need to continue to exist for the write on create,
            until that functionality is officially moved to Studio creation.

            The progress of the above work will be tracked in the following ticket:
            https://openedx.atlassian.net/browse/EDUCATOR-3525.
        """
        end_date = self.end

        if waffle.switch_is_active(PUBLISHER_ENABLE_READ_ONLY_FIELDS):
            discovery_counterpart = self.discovery_counterpart

            if discovery_counterpart and discovery_counterpart.end:
                end_date = discovery_counterpart.end

        return end_date

    @end_date_temporary.setter
    def end_date_temporary(self, value):
        if waffle.switch_is_active(PUBLISHER_ENABLE_READ_ONLY_FIELDS):
            raise CourseRunEditException
        else:
            self.end = value


class Seat(TimeStampedModel, ChangedByMixin):
    HONOR = 'honor'
    AUDIT = 'audit'
    VERIFIED = 'verified'
    PROFESSIONAL = 'professional'
    NO_ID_PROFESSIONAL = 'no-id-professional'
    CREDIT = 'credit'
    PAID_SEATS = [VERIFIED, PROFESSIONAL, CREDIT]
    PAID_AND_AUDIT_APPLICABLE_SEATS = [CREDIT, VERIFIED]

    SEAT_TYPE_CHOICES = (
        (HONOR, _('Honor')),
        (AUDIT, _('Audit')),
        (VERIFIED, _('Verified')),
        (PROFESSIONAL, _('Professional (with ID verification)')),
        (NO_ID_PROFESSIONAL, _('Professional (no ID verification)')),
        (CREDIT, _('Credit')),
    )

    PRICE_FIELD_CONFIG = {
        'decimal_places': 2,
        'max_digits': 10,
        'null': False,
        'default': 0.00,
    }
    course_run = models.ForeignKey(CourseRun, related_name='seats')
    type = models.CharField(max_length=63, choices=SEAT_TYPE_CHOICES, verbose_name='Seat type')
    price = models.DecimalField(**PRICE_FIELD_CONFIG)
    currency = models.ForeignKey(Currency, default='USD', related_name='publisher_seats')
    upgrade_deadline = models.DateTimeField(null=True, blank=True)
    credit_provider = models.CharField(max_length=255, null=True, blank=True)
    credit_hours = models.IntegerField(null=True, blank=True)
    credit_price = models.DecimalField(**PRICE_FIELD_CONFIG)

    history = HistoricalRecords()

    def __str__(self):
        return '{course}: {type}'.format(course=self.course_run.course.title, type=self.type)

    @property
    def is_valid_seat(self):
        """
        Check that seat is valid or not.
        """
        return (
            self.type == self.AUDIT or
            (self.type in [self.VERIFIED, self.PROFESSIONAL] and self.price > 0) or
            (self.type == self.CREDIT and self.credit_price > 0 and self.price > 0)
        )

    @property
    def calculated_upgrade_deadline(self):
        """ Returns upgraded deadline calculated using edX business logic.

        Only verified seats have upgrade deadlines. If the instance does not have an upgrade deadline set, the value
        will be calculated based on the related course run's end date.
        """
        if self.type == self.VERIFIED:
            if self.upgrade_deadline:
                return self.upgrade_deadline

            deadline = self.course_run.end - datetime.timedelta(days=settings.PUBLISHER_UPGRADE_DEADLINE_DAYS)
            deadline = deadline.replace(hour=23, minute=59, second=59, microsecond=99999)
            return deadline

        return None


class CourseEntitlement(TimeStampedModel):
    VERIFIED = 'verified'
    PROFESSIONAL = 'professional'

    COURSE_MODE_CHOICES = (
        (VERIFIED, _('Verified')),
        (PROFESSIONAL, _('Professional'))
    )

    PRICE_FIELD_CONFIG = {
        'decimal_places': 2,
        'max_digits': 10,
        'null': False,
        'default': 0.00,
    }

    MODE_TO_SEAT_TYPE_MAPPING = {
        VERIFIED: Seat.VERIFIED,
        PROFESSIONAL: Seat.PROFESSIONAL
    }

    course = models.ForeignKey(Course, related_name='entitlements')
    mode = models.CharField(max_length=63, choices=COURSE_MODE_CHOICES, verbose_name='Course mode')
    price = models.DecimalField(**PRICE_FIELD_CONFIG)
    currency = models.ForeignKey(Currency, default='USD', related_name='publisher_entitlements')

    class Meta(object):
        unique_together = (
            ('course', 'mode')
        )


class UserAttributes(TimeStampedModel):
    """ Record additional metadata about a user. """
    user = models.OneToOneField(User, related_name='attributes')
    enable_email_notification = models.BooleanField(default=True)

    def __str__(self):
        return '{user}: {email_notification}'.format(
            user=self.user, email_notification=self.enable_email_notification
        )

    class Meta:
        verbose_name_plural = 'UserAttributes'


class OrganizationUserRole(TimeStampedModel):
    """ User Roles model for Organization. """

    organization = models.ForeignKey(Organization, related_name='organization_user_roles')
    user = models.ForeignKey(User, related_name='organization_user_roles')
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
    course = models.ForeignKey(Course, related_name='course_user_roles')
    user = models.ForeignKey(User, related_name='course_user_roles')
    role = models.CharField(
        max_length=63, choices=PublisherUserRole.choices, verbose_name=_('Course Role')
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

    @classmethod
    def add_course_roles(cls, course, role, user):
        """
        Create course roles.

        Arguments:
            course (obj): course object
            role (str): role description
            user (obj): User object

        Returns:
            obj: CourseUserRole object

        """
        return cls.objects.get_or_create(course=course, role=role, user=user)


class OrganizationExtension(TimeStampedModel):
    """ Organization-Extension relation model. """
    EDIT_COURSE = 'publisher_edit_course'
    EDIT_COURSE_RUN = 'publisher_edit_course_run'
    VIEW_COURSE = 'publisher_view_course'
    VIEW_COURSE_RUN = 'publisher_view_course_run'

    organization = models.OneToOneField(Organization, related_name='organization_extension')
    group = models.OneToOneField(Group, related_name='organization_extension')

    auto_create_in_studio = models.BooleanField(
        default=True,
        verbose_name=_('Automatically create a run in Studio'),
        help_text=_(
            "When this flag is enabled, creation of a new course run in Publisher"
            " will also create a corresponding course run in Studio."
        )
    )

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
    course = models.OneToOneField(Course, related_name='course_state')
    owner_role_modified = models.DateTimeField(auto_now_add=True, null=True, blank=True)
    marketing_reviewed = models.BooleanField(default=False)

    history = HistoricalRecords()

    # course team status
    Draft = _('Draft')
    SubmittedForMarketingReview = _('Submitted for Marketing Review')
    ApprovedByCourseTeam = _('Approved by Course Team')
    AwaitingCourseTeamReview = _('Awaiting Course Team Review')

    # internal user status
    NotAvailable = _('N/A')
    AwaitingMarketingReview = _('Awaiting Marketing Review')
    ApprovedByMarketing = _('Approved by Marketing')

    def __str__(self):
        return self.get_name_display()

    def can_send_for_review(self):
        """
        Validate minimum required fields before sending for review.
        """
        course = self.course
        return all([
            course.title, course.number, course.short_description, course.full_description,
            course.organizations.first(), course.level_type, course.expected_learnings,
            course.primary_subject, course.image, course.course_team_admin
        ])

    @transition(field=name, source='*', target=CourseStateChoices.Draft)
    def draft(self):
        # TODO: send email etc.
        pass

    @transition(
        field=name,
        source=CourseStateChoices.Draft,
        target=CourseStateChoices.Review,
        conditions=[can_send_for_review]
    )
    def review(self):
        # TODO: send email etc.
        pass

    @transition(field=name, source=CourseStateChoices.Review, target=CourseStateChoices.Approved)
    def approved(self):
        # TODO: send email etc.
        pass

    def change_state(self, state, user, site=None):
        """
        Change course workflow state and ownership also send emails if required.
        """
        is_notifications_enabled = waffle.switch_is_active('enable_publisher_email_notifications')
        if state == CourseStateChoices.Draft:
            self.draft()
        elif state == CourseStateChoices.Review:
            user_role = self.course.course_user_roles.get(user=user)
            if user_role.role == PublisherUserRole.MarketingReviewer:
                self.change_owner_role(PublisherUserRole.CourseTeam)
                self.marketing_reviewed = True
            elif user_role.role == PublisherUserRole.CourseTeam:
                self.change_owner_role(PublisherUserRole.MarketingReviewer)
                if is_notifications_enabled:
                    emails.send_email_for_seo_review(self.course, site)

            self.review()

            if is_notifications_enabled:
                emails.send_email_for_send_for_review(self.course, user, site)

        elif state == CourseStateChoices.Approved:
            user_role = self.course.course_user_roles.get(user=user)
            self.approved_by_role = user_role.role
            self.marketing_reviewed = True
            self.approved()

            if is_notifications_enabled:
                emails.send_email_for_mark_as_reviewed(self.course, user, site)

        self.save()

    @property
    def is_approved(self):
        """ Check that course is approved or not."""
        return self.name == CourseStateChoices.Approved

    def change_owner_role(self, role):
        """
        Change ownership role.
        """
        self.owner_role = role
        self.owner_role_modified = timezone.now()
        self.save()

    @property
    def is_draft(self):
        """ Check that course is in Draft state or not."""
        return self.name == CourseStateChoices.Draft

    @property
    def is_in_review(self):
        """ Check that course is in Review state or not."""
        return self.name == CourseStateChoices.Review

    @property
    def course_team_status(self):
        if self.is_draft and self.owner_role == PublisherUserRole.CourseTeam and not self.marketing_reviewed:
            return self.Draft
        elif self.owner_role == PublisherUserRole.MarketingReviewer:
            return self.SubmittedForMarketingReview
        elif self.owner_role == PublisherUserRole.CourseTeam and self.is_approved:
            return self.ApprovedByCourseTeam
        elif self.marketing_reviewed and self.owner_role == PublisherUserRole.CourseTeam:
            return self.AwaitingCourseTeamReview

    @property
    def internal_user_status(self):
        if self.is_draft and self.owner_role == PublisherUserRole.CourseTeam:
            return self.NotAvailable
        elif self.owner_role == PublisherUserRole.MarketingReviewer and (self.is_in_review or self.is_draft):
            return self.AwaitingMarketingReview
        elif self.marketing_reviewed:
            return self.ApprovedByMarketing


class CourseRunState(TimeStampedModel, ChangedByMixin):
    """ Publisher Workflow Course Run State Model. """

    name = FSMField(default=CourseRunStateChoices.Draft, choices=CourseRunStateChoices.choices)
    approved_by_role = models.CharField(blank=True, null=True, max_length=63, choices=PublisherUserRole.choices)
    owner_role = models.CharField(max_length=63, choices=PublisherUserRole.choices)
    course_run = models.OneToOneField(CourseRun, related_name='course_run_state')
    owner_role_modified = models.DateTimeField(auto_now_add=True, null=True, blank=True)
    preview_accepted = models.BooleanField(default=False)

    history = HistoricalRecords()

    def can_send_for_review(self):
        """
        Validate minimum required fields before sending for review.
        """
        course_run = self.course_run
        return all([
            course_run.course.course_state.is_approved, course_run.has_valid_seats, course_run.start_date_temporary,
            course_run.end, course_run.pacing_type_temporary, course_run.has_valid_staff,
            course_run.is_valid_micromasters, course_run.is_valid_professional_certificate,
            course_run.is_valid_xseries, course_run.language, course_run.transcript_languages.all(),
            course_run.lms_course_id, course_run.min_effort, course_run.video_language, course_run.length

        ])

    def __str__(self):
        return self.get_name_display()

    @transition(field=name, source='*', target=CourseRunStateChoices.Draft)
    def draft(self):
        # TODO: send email etc.
        pass

    @transition(
        field=name,
        source=CourseRunStateChoices.Draft,
        target=CourseRunStateChoices.Review,
        conditions=[can_send_for_review]
    )
    def review(self):
        # TODO: send email etc.
        pass

    @transition(field=name, source=CourseRunStateChoices.Review, target=CourseRunStateChoices.Approved)
    def approved(self):
        # TODO: send email etc.
        pass

    @transition(field=name, source=CourseRunStateChoices.Approved, target=CourseRunStateChoices.Published)
    def published(self, site):
        # Grab some variables, bailing if anything doesn't make sense
        publisher_run = self.course_run
        discovery_run = publisher_run and publisher_run.discovery_course_run
        discovery_course = discovery_run and discovery_run.course
        if not discovery_course:
            return

        now = datetime.datetime.now(pytz.UTC)

        # Publish new course
        discovery_run.announcement = now
        discovery_run.status = CourseRunStatus.Published
        discovery_run.save()

        # Now, find old course runs that are no longer active but still published.
        # These will be unpublished in favor of the new course.
        for run in discovery_course.course_runs.all():
            if run != discovery_run and run.status == CourseRunStatus.Published and run.end and run.end < now:
                CourseRunMarketingSitePublisher(site.partner).add_url_redirect(discovery_run, run)
                run.status = CourseRunStatus.Unpublished
                run.save()

        # Notify course team
        if waffle.switch_is_active('enable_publisher_email_notifications'):
            emails.send_course_run_published_email(self.course_run, site)

    def change_state(self, state, user, site=None):
        """
        Change course run workflow state and ownership also send emails if required.
        """
        if state == CourseRunStateChoices.Draft:
            self.draft()
        elif state == CourseRunStateChoices.Review:
            user_role = self.course_run.course.course_user_roles.get(user=user)
            if user_role.role == PublisherUserRole.ProjectCoordinator:
                self.change_owner_role(PublisherUserRole.CourseTeam)
            elif user_role.role == PublisherUserRole.CourseTeam:
                self.change_owner_role(PublisherUserRole.ProjectCoordinator)

            self.review()

            if waffle.switch_is_active('enable_publisher_email_notifications'):
                emails.send_email_for_send_for_review_course_run(self.course_run, user, site)

        elif state == CourseRunStateChoices.Approved:
            user_role = self.course_run.course.course_user_roles.get(user=user)
            self.approved_by_role = user_role.role
            self.change_owner_role(PublisherUserRole.CourseTeam)
            self.approved()

            if waffle.switch_is_active('enable_publisher_email_notifications'):
                emails.send_email_for_mark_as_reviewed_course_run(self.course_run, user, site)
                emails.send_email_to_publisher(self.course_run, user, site)
                emails.send_email_preview_page_is_available(self.course_run, site)

        elif state == CourseRunStateChoices.Published:
            self.published(site)

        self.save()

    def change_owner_role(self, role):
        """
        Change ownership role.
        """
        self.owner_role = role
        self.owner_role_modified = timezone.now()
        self.save()

    @property
    def is_preview_accepted(self):
        """ Check that preview is accepted or not."""
        return self.preview_accepted

    @property
    def is_approved(self):
        """ Check that course run is approved or not."""
        return self.name == CourseRunStateChoices.Approved

    @property
    def is_ready_to_publish(self):
        """ Check that course run is ready to publish or not."""
        return self.is_approved and self.is_preview_accepted

    @property
    def is_published(self):
        """ Check that course run is published or not."""
        return self.name == CourseRunStateChoices.Published

    @property
    def is_draft(self):
        """ Check that course run is in Draft state or not."""
        return self.name == CourseRunStateChoices.Draft

    @property
    def is_in_review(self):
        """ Check that course run is in Review state or not."""
        return self.name == CourseRunStateChoices.Review

    @property
    def preview_status_for_publisher(self):
        """
        Calculate the preview status review, accepted or decline for publisher user
        """
        if self.owner_role == PublisherUserRole.CourseTeam:
            return _('Submitted for review')
        elif self.owner_role == PublisherUserRole.Publisher and self.preview_accepted:
            return _('Preview Accepted')
        return _('Preview Declined')


class PublisherUser(User):
    """ Publisher User Proxy Model. """

    class Meta:
        proxy = True

    @staticmethod
    def get_courses(user, queryset=None):
        if queryset is None:
            queryset = Course.objects.all()

        if is_publisher_admin(user):
            return queryset
        elif is_internal_user(user):
            return queryset.filter(course_user_roles__user=user).distinct()
        else:
            organizations = get_objects_for_user(
                user,
                OrganizationExtension.VIEW_COURSE,
                OrganizationExtension,
                use_groups=True,
                with_superuser=False
            ).values_list('organization')
            return queryset.filter(organizations__in=organizations)


class DrupalLoaderConfig(SingletonModel):
    """
    Configuration for data loaders used in the load_drupal_data command.
    """
    course_run_ids = models.TextField(default=None, null=False, blank=False, verbose_name=_('Course Run IDs'))
    partner_code = models.TextField(default=None, null=False, blank=False, verbose_name=_('Partner Code'))
    load_unpublished_course_runs = models.BooleanField(default=False)
