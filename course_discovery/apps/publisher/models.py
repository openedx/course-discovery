import logging
from django.contrib.auth.models import Group

from django.core.urlresolvers import reverse
from django.db import models
from django.db.models.signals import pre_save
from django.dispatch import receiver
from django.utils.translation import ugettext_lazy as _
from django_extensions.db.models import TimeStampedModel
from django_fsm import FSMField, transition
from guardian.shortcuts import assign_perm, get_groups_with_perms, get_users_with_perms
from simple_history.models import HistoricalRecords
from sortedm2m.fields import SortedManyToManyField
from stdimage.models import StdImageField
from taggit.managers import TaggableManager
import waffle

from course_discovery.apps.core.models import User, Currency
from course_discovery.apps.course_metadata.choices import CourseRunPacing
from course_discovery.apps.course_metadata.models import LevelType, Subject, Person, Organization
from course_discovery.apps.course_metadata.utils import UploadToFieldNamePath
from course_discovery.apps.ietf_language_tags.models import LanguageTag
from course_discovery.apps.publisher.emails import send_email_for_change_state

logger = logging.getLogger(__name__)


class ChangedByMixin(models.Model):
    changed_by = models.ForeignKey(User, null=True, blank=True)

    class Meta:
        abstract = True


class State(TimeStampedModel, ChangedByMixin):
    """ Publisher Workflow State Model. """

    DRAFT = 'draft'
    NEEDS_REVIEW = 'needs_review'
    NEEDS_FINAL_APPROVAL = 'needs_final_approval'
    FINALIZED = 'finalized'
    PUBLISHED = 'published'
    CHOICES = (
        (DRAFT, _('Draft')),
        (NEEDS_REVIEW, _('Needs Review')),
        (NEEDS_FINAL_APPROVAL, _('Needs Final Approval')),
        (FINALIZED, _('Finalized')),
        (PUBLISHED, _('Published'))
    )

    name = FSMField(default=DRAFT, choices=CHOICES)

    history = HistoricalRecords()

    def __str__(self):
        return self.get_name_display()

    @transition(field=name, source='*', target=DRAFT)
    def draft(self):
        # TODO: send email etc.
        pass

    @transition(field=name, source=DRAFT, target=NEEDS_REVIEW)
    def needs_review(self):
        # TODO: send email etc.
        pass

    @transition(field=name, source=NEEDS_REVIEW, target=NEEDS_FINAL_APPROVAL)
    def needs_final_approval(self):
        # TODO: send email etc.
        pass

    @transition(field=name, source=NEEDS_FINAL_APPROVAL, target=FINALIZED)
    def finalized(self):
        # TODO: send email etc.
        pass

    @transition(field=name, source=FINALIZED, target=PUBLISHED)
    def publish(self):
        # TODO: send email etc.
        pass


class Course(TimeStampedModel, ChangedByMixin):
    """ Publisher Course model. It contains fields related to the course intake form."""
    VIEW_PERMISSION = 'view_course'
    COORDINATOR = 'partner_coordinator'
    REVIEWER = 'reviewer'
    PUBLISHER = 'publisher'


    title = models.CharField(max_length=255, default=None, null=True, blank=True, verbose_name=_('Course title'))
    number = models.CharField(max_length=50, null=True, blank=True, verbose_name=_('Course number'))
    short_description = models.CharField(
        max_length=255, default=None, null=True, blank=True, verbose_name=_('Brief Description')
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
    learner_testimonial = models.CharField(max_length=50, null=True, blank=True)
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

    team_admin = models.ForeignKey(User, null=True, blank=True, related_name='team_admin_user')
    image = StdImageField(
        upload_to=UploadToFieldNamePath(
            populate_from='number',
            path='media/publisher/courses/images'
        ),
        blank=True,
        null=True,
        variations={
            'large': (2120, 1192),
            'medium': (1440, 480),
            'thumbnail': (100, 100, True),
        }
    )

    is_seo_review = models.BooleanField(default=False)
    keywords = TaggableManager(blank=True, verbose_name='keywords')

    history = HistoricalRecords()

    def __str__(self):
        return self.title

    @property
    def post_back_url(self):
        return reverse('publisher:publisher_courses_edit', kwargs={'pk': self.id})

    def assign_permission_by_group(self, institution):
        """ Assigns permission on the course against the group. """

        assign_perm(self.VIEW_PERMISSION, institution, self)

    @property
    def group_institution(self):
        """ Returns the group object having permissions on the given course.
        Course will be associated with one group only.
        """
        available_groups = get_groups_with_perms(self)
        return available_groups[0] if available_groups else None

    def assign_permission_by_role(self, role, user):
        """ Assigns permission on the course against the role and user. """
        assign_perm(role, user, self)

    @property
    def has_group_permissions(self):
        """ check whether user belongs to valid group using the
        course group and user group.
        """
        # https://pythonhosted.org/django-guardian/api/guardian.shortcuts.html#get-users-with-perms

        # with group_users it will return the all users having permissions on that object.

        # return (dict): {<User: admin>, <User: waheed>}
        return get_users_with_perms(self, attach_perms=False, with_superusers=False, with_group_users=True)

    @property
    def has_role_permissions(self):
        """ Returns the user object having permissions on the given course."""
        # https://pythonhosted.org/django-guardian/api/guardian.shortcuts.html#get-users-with-perms

        # return (dict): {<User: admin>: ['coordinator', 'publisher'], <User: waheed>: ['reviewer']}
        return get_users_with_perms(self, attach_perms=True, with_superusers=False, with_group_users=False)

    def get_group_users_emails(self):
        """ Returns the list of users emails with enable email notifications
        against a course group. By default if attribute value does not exists
        then user will be eligible for emails.
        """
        users_list = get_users_with_perms(self)
        emails = [
            user.email for user in users_list
            if not hasattr(user, 'attributes') or user.attributes.enable_email_notification
        ]
        return emails

    @property
    def keywords_data(self):
        keywords = self.keywords.all()
        if keywords:
            return ', '.join(k.name for k in keywords)

        return None


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

    state = models.ForeignKey(State, null=True, blank=True)

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

    history = HistoricalRecords()

    def __str__(self):
        return '{course}: {start_date}'.format(course=self.course.title, start_date=self.start)

    def change_state(self, target=State.DRAFT, user=None):
        if target == State.NEEDS_REVIEW:
            self.state.needs_review()
        elif target == State.NEEDS_FINAL_APPROVAL:
            self.state.needs_final_approval()
        elif target == State.FINALIZED:
            self.state.finalized()
        elif target == State.PUBLISHED:
            self.state.publish()
        else:
            self.state.draft()

        if user:
            self.state.changed_by = user

        self.state.save()

        if waffle.switch_is_active('enable_publisher_email_notifications'):
            send_email_for_change_state(self)

    @property
    def current_state(self):
        return self.state.get_name_display()

    @property
    def post_back_url(self):
        return reverse('publisher:publisher_course_runs_edit', kwargs={'pk': self.id})

    class Meta(TimeStampedModel.Meta):
        permissions = (
            ('partner_coordinator', 'partner coordinator'),
            ('reviewer', 'reviewer'),
            ('publisher', 'publisher'),
        )

    def assign_permission_by_default_org_users(self, institution):
        """ Assigns permission on the course against the group. """
        default_users = institution.organization.organization.roles.all()
        for role in default_users:
            assign_perm(role.role, role.user, self)

    @property
    def user_permissions(self):
        """ Returns the user object having permissions on the given course."""
        # https://pythonhosted.org/django-guardian/api/guardian.shortcuts.html#get-users-with-perms

        # return (dict): {<User: admin>: ['coordinator', 'publisher'], <User: waheed>: ['reviewer']}
        return get_users_with_perms(self, attach_perms=True, with_superusers=False, with_group_users=False)

    @property
    def has_group_permissions(self):
        """ check whether user belongs to valid group using the
        course group and user group.
        """
        # https://pythonhosted.org/django-guardian/api/guardian.shortcuts.html#get-users-with-perms

        # with group_users it will return the all users having permissions on that object.

        # return (dict): {<User: admin>, <User: waheed>}
        return get_users_with_perms(self, attach_perms=False, with_superusers=False, with_group_users=True)


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

    history = HistoricalRecords()

    def __str__(self):
        return '{course}: {type}'.format(course=self.course_run.course.title, type=self.type)

    @property
    def post_back_url(self):
        return reverse('publisher:publisher_seats_edit', kwargs={'pk': self.id})


@receiver(pre_save, sender=CourseRun)
def initialize_workflow(sender, instance, **kwargs):    # pylint: disable=unused-argument
    """ Create Workflow State For CourseRun Before Saving. """
    create_workflow_state(instance)


def create_workflow_state(course_run):
    """ Create Workflow State If Not Present."""
    if not course_run.state:
        state = State()
        state.save()
        course_run.state = state


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


class OrganizationsGroup(TimeStampedModel):
    organization = models.OneToOneField(Organization, related_name='group')
    group = models.OneToOneField(Group, related_name='organization')


class OrganizationsRoles(TimeStampedModel):
    """ Organization model for roles. """
    COORDINATOR = 'partner_coordinator'
    REVIEWER = 'reviewer'
    PUBLISHER = 'publisher'

    ROLES_TYPE_CHOICES = (
        (COORDINATOR, _('Partner Coordinator')),
        (REVIEWER, _('Reviewer')),
        (PUBLISHER, _('Publisher')),
    )

    organization = models.ForeignKey(Organization, related_name='roles')
    user = models.ForeignKey(User, related_name='organizations_roles')
    role = models.CharField(max_length=63, choices=ROLES_TYPE_CHOICES, verbose_name='Role Type')

    history = HistoricalRecords()

    def __str__(self):
        return '{organization}'.format(
            organization=self.organization
        )

    class Meta:
        unique_together = (
            ('organization', 'user', 'role'),
        )
        verbose_name_plural = 'Organizations'

    # @classmethod
    # def organization_users(cls, organization):
    #     """
    #     Returns:
    #         QuerySet
    #     """
    #     from nose.tools import set_trace; set_trace()
    #     group_objects = cls.objects.filter(organization=organization)
    #
