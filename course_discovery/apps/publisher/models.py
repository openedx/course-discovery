import logging
from urllib.parse import urljoin

import waffle
from django.contrib.auth.models import Group
from django.db import models
from django.urls import reverse
from django.utils import timezone
from django.utils.translation import ugettext_lazy as _
from django_extensions.db.models import TimeStampedModel
from django_fsm import FSMField, transition
from simple_history.models import HistoricalRecords
from sortedm2m.fields import SortedManyToManyField
from stdimage.models import StdImageField
from taggit.managers import TaggableManager

from course_discovery.apps.core.models import Currency, User
from course_discovery.apps.course_metadata.choices import CourseRunPacing
from course_discovery.apps.course_metadata.models import LevelType, Organization, Person, Subject
from course_discovery.apps.course_metadata.utils import UploadToFieldNamePath
from course_discovery.apps.ietf_language_tags.models import LanguageTag
from course_discovery.apps.publisher import emails
from course_discovery.apps.publisher.choices import (CourseRunStateChoices, CourseStateChoices, InternalUserRole,
                                                     PublisherUserRole)
from course_discovery.apps.publisher.utils import is_email_notification_enabled
from course_discovery.apps.publisher.validators import ImageSizeValidator

logger = logging.getLogger(__name__)


class ChangedByMixin(models.Model):
    changed_by = models.ForeignKey(User, null=True, blank=True)

    class Meta:
        abstract = True


class Course(TimeStampedModel, ChangedByMixin):
    """ Publisher Course model. It contains fields related to the course intake form."""

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
    verification_deadline = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name=_("Verification deadline"),
        help_text=_('Last date/time on which verification for this product can be submitted.')
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
        variations={
            'thumbnail': (100, 100, True),
        },
        validators=[ImageSizeValidator(width=2120, height=1192)]
    )

    is_seo_review = models.BooleanField(default=False)
    keywords = TaggableManager(blank=True, verbose_name='keywords')
    faq = models.TextField(default=None, null=True, blank=True, verbose_name=_('FAQ'))
    video_link = models.URLField(default=None, null=True, blank=True, verbose_name=_('Video Link'))

    # temp fields for data migrations only.
    course_metadata_pk = models.PositiveIntegerField(null=True, blank=True, verbose_name=_('Course Metadata Course PK'))

    history = HistoricalRecords()

    def __str__(self):
        return self.title

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
        users_list_roles = [obj.user for obj in self.course_user_roles.all()]

        user_emails = [user.email for user in users_list_roles if is_email_notification_enabled(user)]

        return user_emails

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
    def course_image_url(self):
        """
        Return course image url.
        """

        if self.image:
            return self.image.url

        course_run = self.course_runs.filter(course_run_state__name=CourseRunStateChoices.Published).first()
        if course_run and course_run.card_image_url:
            return course_run.card_image_url

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

    course = models.ForeignKey(Course, related_name='publisher_course_runs')
    lms_course_id = models.CharField(max_length=255, unique=True, null=True, blank=True)

    start = models.DateTimeField(null=True, blank=True)
    end = models.DateTimeField(null=True, blank=True)
    enrollment_start = models.DateTimeField(null=True, blank=True)
    enrollment_end = models.DateTimeField(null=True, blank=True)
    certificate_generation = models.DateTimeField(null=True, blank=True)
    pacing_type = models.CharField(
        max_length=255, db_index=True, null=True, blank=True, choices=CourseRunPacing.choices,
        validators=[CourseRunPacing.validator]
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
    preview_url = models.URLField(null=True, blank=True)

    # temporary field to save the canonical course run image. In 2nd script this url field
    # will be used to download the image and save into course model --> course image.
    card_image_url = models.URLField(null=True, blank=True, verbose_name='canonical course run image')

    short_description_override = models.CharField(
        max_length=255, default=None, null=True, blank=True,
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

    history = HistoricalRecords()

    def __str__(self):
        return '{course}: {start_date}'.format(course=self.course.title, start_date=self.start)

    @property
    def post_back_url(self):
        return reverse('publisher:publisher_course_runs_edit', kwargs={'pk': self.id})

    @property
    def created_by(self):
        history_user = self.history.order_by('history_date').first().history_user     # pylint: disable=no-member
        if history_user:
            return history_user.get_full_name() or history_user.username

        return

    @property
    def studio_url(self):
        if self.lms_course_id and self.course.partner and self.course.partner.studio_url:
            path = 'course/{lms_course_id}'.format(lms_course_id=self.lms_course_id)
            return urljoin(self.course.partner.studio_url, path)

        return None

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


class Seat(TimeStampedModel, ChangedByMixin):
    """ Seat model. """
    HONOR = 'honor'
    AUDIT = 'audit'
    VERIFIED = 'verified'
    PROFESSIONAL = 'professional'
    NO_ID_PROFESSIONAL = 'no-id-professional'
    CREDIT = 'credit'

    SEAT_TYPE_CHOICES = (
        (HONOR, _('Honor')),
        (AUDIT, _('Audit')),
        (VERIFIED, _('Verified')),
        (PROFESSIONAL, _('Professional (with ID verification)')),
        (NO_ID_PROFESSIONAL, _('Professional (no ID verifiation)')),
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

    def change_state(self, state, user):
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
                    emails.send_email_for_seo_review(self.course)

            self.review()

            if is_notifications_enabled:
                emails.send_email_for_send_for_review(self.course, user)

        elif state == CourseStateChoices.Approved:
            user_role = self.course.course_user_roles.get(user=user)
            self.approved_by_role = user_role.role
            self.marketing_reviewed = True
            self.approved()

            if is_notifications_enabled:
                emails.send_email_for_mark_as_reviewed(self.course, user)

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
            return {'status_text': _('In Draft since'), 'date': self.owner_role_modified}
        elif self.owner_role == PublisherUserRole.MarketingReviewer:
            return {'status_text': _('Submitted on'), 'date': self.owner_role_modified}
        elif self.owner_role == PublisherUserRole.CourseTeam and self.is_approved:
            return {'status_text': _('Reviewed on'), 'date': self.owner_role_modified}
        elif self.marketing_reviewed and self.owner_role == PublisherUserRole.CourseTeam:
            return {'status_text': _('In Review since'), 'date': self.owner_role_modified}

    @property
    def internal_user_status(self):
        if self.is_draft and self.owner_role == PublisherUserRole.CourseTeam:
            return {'status_text': _('n/a'), 'date': ''}
        elif self.owner_role == PublisherUserRole.MarketingReviewer and (self.is_in_review or self.is_draft):
            return {'status_text': _('In Review since'), 'date': self.owner_role_modified}
        elif self.marketing_reviewed:
            return {'status_text': _('Reviewed on'), 'date': self.owner_role_modified}


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
            course_run.course.course_state.is_approved, course_run.has_valid_seats, course_run.start, course_run.end,
            course_run.pacing_type, course_run.has_valid_staff, course_run.is_valid_micromasters,
            course_run.is_valid_professional_certificate, course_run.is_valid_xseries, course_run.language,
            course_run.transcript_languages.all(), course_run.lms_course_id, course_run.min_effort,
            course_run.max_effort, course_run.video_language

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
    def published(self):
        emails.send_course_run_published_email(self.course_run)

    def change_state(self, state, user):
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
                emails.send_email_for_send_for_review_course_run(self.course_run, user)

        elif state == CourseRunStateChoices.Approved:
            user_role = self.course_run.course.course_user_roles.get(user=user)
            self.approved_by_role = user_role.role
            self.change_owner_role(PublisherUserRole.Publisher)
            self.approved()

            if waffle.switch_is_active('enable_publisher_email_notifications'):
                emails.send_email_for_mark_as_reviewed_course_run(self.course_run, user)
                emails.send_email_to_publisher(self.course_run, user)

        elif state == CourseRunStateChoices.Published:
            self.published()

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


class PublisherUser(User):
    """ Publisher User Proxy Model. """

    class Meta:
        proxy = True
