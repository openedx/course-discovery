import logging

import waffle
from django.contrib.auth.models import Permission
from django.core.exceptions import ObjectDoesNotExist
from django.db.models.signals import post_save
from django.dispatch import receiver
from slumber.exceptions import SlumberBaseException

from course_discovery.apps.publisher.models import CourseRun, OrganizationExtension
from course_discovery.apps.publisher.studio_api_utils import StudioAPI

logger = logging.getLogger(__name__)


def get_related_discovery_course_run(publisher_course_run):
    try:
        discovery_course = publisher_course_run.course.discovery_counterpart
        return discovery_course.course_runs.latest('start')
    except ObjectDoesNotExist:
        return


@receiver(post_save, sender=CourseRun)
def create_course_run_in_studio_receiver(sender, instance, created, **kwargs):  # pylint: disable=unused-argument
    if created and waffle.switch_is_active('enable_publisher_create_course_run_in_studio'):
        course = instance.course
        for organization in course.organizations.all():
            try:
                if not organization.organization_extension.auto_create_in_studio:
                    logger.warning(
                        ('Course run [%d] will not be automatically created in studio.'
                         'Organization [%s] has opted out of this feature.'),
                        course.id,
                        organization.key,
                    )
                    return
            except ObjectDoesNotExist:
                logger.exception(
                    'Organization [%s] does not have an associated OrganizationExtension',
                    organization.key,
                )

        partner = course.partner

        if not partner:
            logger.error(
                'Failed to publish course run [%d] to Studio. Related course [%d] has no associated Partner.',
                instance.id, course.id
            )
            return

        logger.info('Publishing course run [%d] to Studio...', instance.id)
        api = StudioAPI(instance.course.partner.studio_api_client)

        discovery_course_run = get_related_discovery_course_run(instance)

        if discovery_course_run:
            try:
                logger.info('Creating a re-run of [%s]...', discovery_course_run.key)
                response = api.create_course_rerun_in_studio(instance, discovery_course_run)
            except SlumberBaseException as ex:
                logger.exception(
                    'Failed to create course re-run [%s] on Studio: %s',
                    discovery_course_run.key,
                    ex.content
                )
                raise
        else:
            try:
                logger.info('Creating a new run of [%s]...', instance.course.key)
                response = api.create_course_run_in_studio(instance)
            except SlumberBaseException as ex:
                logger.exception('Failed to create course run [%s] on Studio: %s', instance.id, ex.content)
                raise

        instance.lms_course_id = response['id']
        instance.save()

        try:
            api.update_course_run_image_in_studio(instance)
        except SlumberBaseException as ex:
            logger.exception(
                'Failed to update Studio image for course run [%s]: %s', instance.lms_course_id, ex.content
            )
        except:  # pylint: disable=bare-except
            logger.exception('Failed to update Studio image for course run [%s]', instance.lms_course_id)

        logger.info('Completed creation of course run [%s] on Studio.', instance.lms_course_id)


@receiver(post_save, sender=OrganizationExtension)
def add_permissions_to_organization_group(sender, instance, created, **kwargs):  # pylint: disable=unused-argument
    if created:
        target_permissions = Permission.objects.filter(
            codename__in=['add_person', 'change_person', 'delete_person']
        )
        instance.group.permissions.add(*target_permissions)
