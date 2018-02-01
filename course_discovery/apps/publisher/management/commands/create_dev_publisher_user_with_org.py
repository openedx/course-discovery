import logging

from django.core.management import BaseCommand

from django.contrib.auth.models import Group

from course_discovery.apps.course_metadata.models import Organization
from course_discovery.apps.publisher.choices import PublisherUserRole
from course_discovery.apps.publisher.models import OrganizationExtension, OrganizationUserRole
from course_discovery.apps.publisher.constants import ADMIN_GROUP_NAME, INTERNAL_USER_GROUP_NAME
from course_discovery.apps.core.models import User

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Adds a dev publisher user to an example org with permissions'

    def add_arguments(self, parser):
        parser.add_argument(
            '--username',
            action='store',
            dest='username',
            default='edx',
            required=False,
            help='Username to add permissions to.'
        )

        parser.add_argument(
            '--organization_name',
            action='store',
            dest='organization_name',
            default='edX',
            required=False,
            help='Username to add permissions to.'
        )

    def handle(self, *args, **options):
        """Adds a dev publisher user to an example org with permissions"""

        # Find the user your want to modify (edx) and set their permissions (active, staff, superuser)
        user = User.objects.get(username=options.get('username'))
        print('Retrieved user {}'.format(user.username))
        user.is_active = True
        user.is_staff = True
        user.is_superuser = True
        # Add the groups you want to the user
        groups = Group.objects.filter(name__in=[ADMIN_GROUP_NAME, INTERNAL_USER_GROUP_NAME])
        for group in groups:
            if group not in user.groups.all():
                print('Added {} group to {} user'.format(group.name, user.username))
                user.groups.add(group)
        # Find the Organization that the user should be a part of
        organization = Organization.objects.get(key=options.get('organization_name'))
        print('Retrieved {} organization'.format(organization.name))

        # Add Organization Course Admin via PublisherOrganizationExtension
        organization_extension, created = OrganizationExtension.objects.get_or_create(
            organization=organization
        )
        if created:
            print('Created new Organization Extension for {}'.format(organization.name))
        else:
            print('Retrieved Organization Extension for {}'.format(organization.name))
        organization_extension.group = Group.objects.get(name=ADMIN_GROUP_NAME)
        organization_extension.auto_create_in_studio = False
        organization_extension.save()
        print('Updated Organization Extension with {} group'.format(ADMIN_GROUP_NAME))

        # Create an OrganizationUserRole if it doesn't exist, setting the role to publisher, organization and user
        organization_user_role, created = OrganizationUserRole.objects.get_or_create(
            user=user,
            organization=organization
        )
        if created:
            print('Created new Organization Role for user {} and organization {}'.format(user.username, organization.name))
            organization_user_role.role = PublisherUserRole.Publisher
            organization_user_role.save()

        user.save()
        print('Successfully granted permissions to {}'.format(user.username))
