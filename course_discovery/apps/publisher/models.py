from django.contrib.auth.models import Group
from django.db import models
from django.utils.translation import ugettext_lazy as _
from django_extensions.db.models import TimeStampedModel
from simple_history.models import HistoricalRecords

from course_discovery.apps.core.models import User
from course_discovery.apps.course_metadata.models import Organization
from course_discovery.apps.publisher.choices import InternalUserRole

# These models might more appropriately live elsewhere, but are here for historical reasons.


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
